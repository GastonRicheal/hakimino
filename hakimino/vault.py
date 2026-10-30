"""Argon2id-derived AES-GCM vault. No plaintext files or stored key/verifier."""
import base64
import binascii
import json
import os
from pathlib import Path
import secrets
import string
import tempfile
from contextlib import contextmanager

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_FILE_BYTES = 8 * 1024 * 1024
KDF = {"name": "argon2id", "version": 19, "memory_kib": 65536,
       "iterations": 3, "parallelism": 1, "key_bytes": 32}
ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"


class VaultError(Exception):
    """Expected failure that is safe to show without exposing secrets."""


def generate_password(length=24):
    if type(length) is not int or not 16 <= length <= 128:
        raise VaultError("Password length must be an integer from 16 to 128.")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VaultError("Duplicate JSON field.")
        result[key] = value
    return result


def _parse(data):
    try:
        return json.loads(data, object_pairs_hook=_unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise VaultError("Invalid vault format.") from exc


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _decode(value, size=None):
    try:
        if not isinstance(value, str):
            raise ValueError()
        raw = base64.b64decode(value, validate=True)
        if _b64(raw) != value or (size is not None and len(raw) != size):
            raise ValueError()
        return raw
    except (ValueError, binascii.Error) as exc:
        raise VaultError("Invalid vault encoding or field length.") from exc


def _derive(password, salt):
    if not isinstance(password, str) or not password or len(password) > 1024:
        raise VaultError("Master password must contain 1 to 1024 characters.")
    return hash_secret_raw(password.encode("utf-8"), salt,
                           time_cost=KDF["iterations"], memory_cost=KDF["memory_kib"],
                           parallelism=KDF["parallelism"], hash_len=32,
                           type=Type.ID, version=19)


def _validate_entries(entries):
    if not isinstance(entries, dict):
        raise VaultError("Invalid vault entries.")
    for label, entry in entries.items():
        if not isinstance(label, str) or not label.strip() or len(label) > 256:
            raise VaultError("Entry label must contain 1 to 256 characters.")
        if not isinstance(entry, dict) or set(entry) != {"username", "password"}:
            raise VaultError("Invalid entry fields.")
        if any(not isinstance(v, str) or len(v) > 4096 for v in entry.values()):
            raise VaultError("Entry fields must be text of at most 4096 characters.")
        if not entry["password"]:
            raise VaultError("Entry password cannot be empty.")


def seal(entries, password):
    """New salt/key and nonce for every complete save; header is authenticated."""
    _validate_entries(entries)
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    header = {"format": "hakimino", "version": 1, "kdf": dict(KDF),
              "salt": _b64(salt), "nonce": _b64(nonce)}
    ciphertext = AESGCM(_derive(password, salt)).encrypt(nonce, _json(entries), _json(header))
    data = _json({**header, "ciphertext": _b64(ciphertext)}) + b"\n"
    if len(data) > MAX_FILE_BYTES:
        raise VaultError("Vault exceeds the 8 MiB size limit.")
    return data


def unseal(data, password):
    if len(data) > MAX_FILE_BYTES:
        raise VaultError("Vault exceeds the 8 MiB size limit.")
    obj = _parse(data)
    if not isinstance(obj, dict) or set(obj) != {"format", "version", "kdf", "salt", "nonce", "ciphertext"}:
        raise VaultError("Invalid vault fields.")
    if obj["format"] != "hakimino" or type(obj["version"]) is not int or obj["version"] != 1:
        raise VaultError("Unsupported vault format or version.")
    # Pin the full profile before Argon2: untrusted files cannot request huge KDF costs.
    if _json(obj["kdf"]) != _json(KDF):
        raise VaultError("Unsupported KDF profile.")
    salt, nonce = _decode(obj["salt"], 16), _decode(obj["nonce"], 12)
    ciphertext = _decode(obj.pop("ciphertext"))
    if len(ciphertext) < 16:
        raise VaultError("Invalid ciphertext length.")
    try:
        cleartext = AESGCM(_derive(password, salt)).decrypt(nonce, ciphertext, _json(obj))
    except InvalidTag as exc:
        raise VaultError("Wrong master password or damaged vault.") from exc
    entries = _parse(cleartext)
    _validate_entries(entries)
    return entries


@contextmanager
def _lock(path):
    """Cooperating processes serialize all operations, including initialization."""
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise VaultError("Vault is busy. If a process crashed, remove its .lock only after checking no process uses it.") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def _write(path, data):
    # The temporary file contains ciphertext only and is on the same filesystem.
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _read(path, password):
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    return unseal(data, password)


def operate(path, password, action, *, label=None, username="", entry_password=None):
    """Read or mutate a vault; no save occurs on failed authentication/validation."""
    path = Path(path).absolute()
    if path.suffix != ".vault":
        raise VaultError("Use a .vault filename (ignored by Git by default).")
    if path.is_symlink():
        raise VaultError("Vault symlinks are not supported.")
    if action not in {"init", "list", "show", "add", "delete"}:
        raise VaultError("Unknown action.")
    with _lock(path):
        if action == "init":
            if path.exists():
                raise VaultError("Vault already exists; initialization never overwrites it.")
            if not isinstance(password, str) or len(password) < 12:
                raise VaultError("Choose a master passphrase of at least 12 characters.")
            _write(path, seal({}, password))
            return None
        entries = _read(path, password)
        if action == "list":
            return sorted(entries)
        if action == "add":
            if label in entries:
                raise VaultError("Entry already exists; delete it explicitly before replacing it.")
            entries[label] = {"username": username, "password": entry_password}
        else:
            if label not in entries:
                raise VaultError("Entry not found.")
            if action == "show":
                return entries[label]
            del entries[label]
        _write(path, seal(entries, password))
        return None
