# hakimino

## Team Members

| Name | Student ID |
| --- | --- |
| ZHANG FANGYUCHEN | 2023901700 |
| LYU SONGYUAN | 2023901706 |

## Project 2: Local Password Manager

Hakimino stores account credentials in a local encrypted vault. A master
passphrase derives an AES-256 key using Argon2id; AES-GCM encrypts and authenticates
the entire collection. A password generator uses Python's `secrets` module.

This is the first local implementation based on Class 7, PDF page 16. The full
course-site brief has not yet been obtained, so CLI format, exact parameters and
additional submission requirements remain to be checked. The slide states a
12 November deadline, teams of 2–3, and that the README accounts for half of the
project mark. No individual contribution split is claimed here.

## Installation and use

Requires Python 3.11 or later. In Windows PowerShell, from this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m hakimino --help
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault init
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault add school --generate
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault list
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault show school
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault show school --reveal
.\.venv\Scripts\python.exe -m hakimino --vault personal.vault delete school
```

Each vault command prompts for the master passphrase without echo. Initialization
requires confirmation and at least 12 characters; use a long, independently
chosen passphrase. This length check alone does not establish password strength.
`add` prompts for the username and, without `--generate`, the account password.
Generated passwords are stored directly without printing them. `show` hides the
password unless `--reveal` is supplied. `delete` requires typing `DELETE`.
Entry labels appear in command history; use non-sensitive aliases.

To generate a standalone password (visible on screen):

```powershell
.\.venv\Scripts\python.exe -m hakimino generate --length 24
```

The parent directory must exist. Use a `.vault` filename so default Git ignore
rules cover it. There is no server, account registration or network dependency
at runtime. On macOS/Linux use `.venv/bin/python` for the equivalent commands.

## Why these security choices

### Master password and key derivation

Argon2id version 19 derives 32 bytes from UTF-8 master-password bytes and a random
16-byte salt. The fixed profile uses 65,536 KiB (64 MiB) memory, three iterations
and one lane. These are initial project choices, not claimed teacher-mandated
parameters. Memory and repeated computation increase the cost of offline guessing;
salt prevents one precomputed result from being reusable across vault snapshots.
Weak master passwords remain guessable.

The raw derived value is the encryption key. It is never written to disk. There
is no separately stored password verifier: successful AES-GCM authentication
validates the derived key and unlocks the vault. Saving that same key as a
"password hash" would expose the encryption key. A wrong password and a corrupted
vault therefore produce the same failure message without returning plaintext.
If the full brief requires a separate login/verifier flow, that will need a
separately designed, domain-separated verification value.

### Confidentiality and integrity

AES-256-GCM protects the whole JSON collection, including labels and usernames.
The library appends a 16-byte authentication tag to the ciphertext and refuses
decryption when authentication fails. The format identifier, version, KDF
profile, salt and nonce form canonical JSON associated data (AAD): they remain
visible but are authenticated. This binds the header to the encrypted contents.

Every save generates a new salt (and hence derived key) plus a new random 12-byte
nonce. Reusing a nonce with the same key breaks GCM's security; fresh independent
randomness makes repetition extremely unlikely, not mathematically impossible.
No counter is reset or derived from timestamps. The implementation uses library
cryptography rather than a custom cipher or authentication-tag implementation.

The reader accepts only the fixed KDF profile before deriving any key, rejects
unknown/duplicate fields and caps the file at 8 MiB. An attacker cannot request
arbitrarily large Argon2 allocations by editing a header. Only validated,
authenticated data reaches entry operations.

### Password generation

`secrets.choice` independently samples each character from 76 distinct letters,
digits and symbols. The default length is 24 (allowed range 16–128), giving about
150 bits of sampling entropy for generated passwords. The generator does not
guarantee every character category appears; this preserves uniform sampling and
avoids inventing site-specific composition requirements. It does not use `random`,
timestamps, counters or a repeatable seed.

### Local storage and failures

Only ciphertext is written to a temporary file beside the destination. The file
is flushed and then atomically replaced, so ordinary write/replace failures do
not replace the previous vault with partial output. A `.lock` file prevents
cooperating CLI processes from changing the same path concurrently. After a crash,
remove a stale lock only after confirming no process still uses that vault.
Initialization never overwrites an existing vault, and adding an existing label
fails explicitly. Failed authentication does not modify the vault.

The implementation requests restrictive file modes on POSIX; Windows access
depends on inherited directory ACLs. Store the vault in your own private folder.
`.gitignore` excludes vault files, encrypted temporary files, locks and the local
Python environment. Ignore rules are not encryption or protection against a
deliberate `git add -f`.

## Threat model and limitations

An attacker who copies the vault sees its approximate size, format and KDF
parameters and can try master-password guesses offline. Argon2 slows those
attempts; it does not stop them. Modified ciphertext, tag, salt or nonce fails
authentication; unsupported metadata fails validation. Formatting-only JSON
changes are accepted because authentication covers canonical field values,
not whitespace or field order.

A valid older vault can be replayed: this format does not provide rollback
detection. There is no recovery if the master password is lost, no cloud sync,
automatic backup, clipboard integration or master-password rotation command.
Keep a separate encrypted backup if needed; it may contain deleted entries.
Atomic replacement is not a guarantee against every hardware or power failure.

An attacker controlling the running machine can read keyboard input or process
memory. Python cannot guarantee erasure of password/key objects. Terminal reveal
and standalone generation can expose passwords in scrollback or redirected output.
Locks coordinate this application; they do not defeat a hostile local user who
can replace files or use alternate path aliases. This coursework prototype has
not received an independent security audit.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary directories and explicitly synthetic credentials. They cover
round-trip decryption, incorrect passwords, ciphertext and tag tampering, modified
salt/nonce, malformed files, invalid/resource-abusive headers, fresh randomness,
entry lifecycle, overwrite refusal, lock contention, failed atomic replacement,
generator validation and CLI secret-display behavior. They do not create a real
personal vault or prove security against every attack.

## Code and references

- `hakimino/vault.py`: key derivation, encryption, format validation and file operations.
- `hakimino/cli.py`: commands and non-echoing interactive prompts.
- `tests/test_vault.py`: repeatable functional and rejection tests.
- Course source: *Class 7 NotesApp Login Fix*, PDF page 16, slide 09.
- [Argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html): raw Argon2 API and parameter units.
- [Cryptography AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM): nonce, tag, AAD and authentication failures.
- [Python secrets](https://docs.python.org/3/library/secrets.html): cryptographic random generation.
