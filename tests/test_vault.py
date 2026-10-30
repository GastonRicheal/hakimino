import base64
import json

import pytest

from hakimino import cli, vault

MASTER = "test-only long master passphrase"
ENTRIES = {"school": {"username": "test-student", "password": "test-only-entry-password"}}


@pytest.fixture(scope="module")
def encrypted():
    return vault.seal(ENTRIES, MASTER)


def test_roundtrip_and_no_plaintext(encrypted):
    assert vault.unseal(encrypted, MASTER) == ENTRIES
    for value in [MASTER, "school", "test-student", "test-only-entry-password"]:
        assert value.encode() not in encrypted


def test_wrong_password(encrypted):
    with pytest.raises(vault.VaultError, match="Wrong master password or damaged vault"):
        vault.unseal(encrypted, "wrong test-only password")


@pytest.mark.parametrize("field", ["salt", "nonce", "ciphertext"])
def test_tampering(encrypted, field):
    obj = json.loads(encrypted)
    value = bytearray(base64.b64decode(obj[field]))
    value[-1] ^= 1  # Includes a tag modification when field is ciphertext.
    obj[field] = base64.b64encode(value).decode()
    with pytest.raises(vault.VaultError):
        vault.unseal(json.dumps(obj).encode(), MASTER)


def test_ciphertext_body_tampering(encrypted):
    obj = json.loads(encrypted)
    value = bytearray(base64.b64decode(obj["ciphertext"]))
    value[0] ^= 1
    obj["ciphertext"] = base64.b64encode(value).decode()
    with pytest.raises(vault.VaultError):
        vault.unseal(json.dumps(obj).encode(), MASTER)


@pytest.mark.parametrize("change", [
    {"version": 2}, {"version": True}, {"format": "other"},
    {"salt": "!"}, {"nonce": "AA=="}, {"ciphertext": "AA=="},
    {"kdf": {**vault.KDF, "memory_kib": 2**40}},
    {"kdf": {**vault.KDF, "parallelism": True}}, {"unexpected": 1},
])
def test_untrusted_header_rejected_before_kdf(encrypted, change, monkeypatch):
    obj = {**json.loads(encrypted), **change}
    def forbidden(*args):
        pytest.fail("KDF must not run for an invalid header")
    monkeypatch.setattr(vault, "_derive", forbidden)
    with pytest.raises(vault.VaultError):
        vault.unseal(json.dumps(obj).encode(), MASTER)


@pytest.mark.parametrize("data", [b"", b"[]", b"null", b"{", b'\xff',
                                    b'{"version":1,"version":1}'])
def test_malformed(data):
    with pytest.raises(vault.VaultError):
        vault.unseal(data, MASTER)


def test_oversize_rejected():
    with pytest.raises(vault.VaultError, match="size limit"):
        vault.unseal(b"x" * (vault.MAX_FILE_BYTES + 1), MASTER)


def test_each_save_refreshes_salt_and_nonce(encrypted):
    second = vault.seal(ENTRIES, MASTER)
    a, b = json.loads(encrypted), json.loads(second)
    for field in ["salt", "nonce", "ciphertext"]:
        assert a[field] != b[field]
    assert vault.unseal(second, MASTER) == ENTRIES


def test_full_lifecycle(tmp_path):
    path = tmp_path / "test.vault"
    vault.operate(path, MASTER, "init")
    assert vault.operate(path, MASTER, "list") == []
    vault.operate(path, MASTER, "add", label="school", **{
        "username": "student", "entry_password": "test-entry-password"})
    assert vault.operate(path, MASTER, "list") == ["school"]
    assert vault.operate(path, MASTER, "show", label="school")["password"] == "test-entry-password"
    vault.operate(path, MASTER, "delete", label="school")
    assert vault.operate(path, MASTER, "list") == []
    assert not list(tmp_path.glob("*.lock"))
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("action,kwargs", [
    ("init", {}), ("delete", {"label": "missing"}),
    ("add", {"label": "school", "entry_password": "new"}),
    ("add", {"label": "new", "entry_password": ""}),
])
def test_failed_mutation_preserves_file(tmp_path, encrypted, action, kwargs):
    path = tmp_path / "test.vault"
    path.write_bytes(encrypted)
    with pytest.raises(vault.VaultError):
        vault.operate(path, MASTER, action, **kwargs)
    assert path.read_bytes() == encrypted


def test_wrong_password_does_not_modify_file(tmp_path, encrypted):
    path = tmp_path / "test.vault"
    path.write_bytes(encrypted)
    with pytest.raises(vault.VaultError):
        vault.operate(path, "wrong", "delete", label="school")
    assert path.read_bytes() == encrypted


def test_lock_blocks_other_process(tmp_path, encrypted):
    path = tmp_path / "test.vault"
    path.write_bytes(encrypted)
    lock = tmp_path / "test.vault.lock"
    lock.touch()
    with pytest.raises(vault.VaultError, match="busy"):
        vault.operate(path, MASTER, "delete", label="school")
    assert lock.exists()
    assert path.read_bytes() == encrypted


def test_replace_failure_preserves_original(tmp_path, encrypted, monkeypatch):
    path = tmp_path / "test.vault"
    path.write_bytes(encrypted)
    def fail(*args):
        raise OSError("simulated replace failure")
    monkeypatch.setattr(vault.os, "replace", fail)
    with pytest.raises(OSError):
        vault.operate(path, MASTER, "delete", label="school")
    assert path.read_bytes() == encrypted
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("length", [15, 129, True, 24.5])
def test_generator_rejects_invalid_length(length):
    with pytest.raises(vault.VaultError):
        vault.generate_password(length)


def test_generator_uses_secrets(monkeypatch):
    seen = []
    def choice(alphabet):
        seen.append(alphabet)
        return "A"
    monkeypatch.setattr(vault.secrets, "choice", choice)
    assert vault.generate_password() == "A" * 24
    assert seen == [vault.ALPHABET] * 24


def test_cli_hides_password_by_default(tmp_path, encrypted, monkeypatch, capsys):
    path = tmp_path / "test.vault"
    path.write_bytes(encrypted)
    monkeypatch.setattr(cli, "secret", lambda _: MASTER)
    args = ["--vault", str(path), "show", "school"]
    assert cli.main(args) == 0
    assert "test-only-entry-password" not in capsys.readouterr().out
    assert cli.main(args + ["--reveal"]) == 0
    assert "test-only-entry-password" in capsys.readouterr().out


def test_cli_refuses_echo_fallback(monkeypatch):
    import warnings
    def fallback(_):
        warnings.warn("echo unavailable", cli.getpass.GetPassWarning)
        pytest.fail("Must stop before reading a secret without echo protection")
    monkeypatch.setattr(cli.getpass, "getpass", fallback)
    assert cli.main(["init"]) == 1
