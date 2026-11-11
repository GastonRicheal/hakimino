# Hakimino — Project 2 demonstration script

**Presentation date:** 12 November 2026
**Functional rehearsal baseline:** `666ead44ab8b60b61bb25f44f57a55b75589d6c2`
**Final web polish:** see [follow-up verification](verification/web-polish-2026-11-11.md)
**Suggested length:** 8–10 minutes, plus questions
**Primary interface:** desktop; CLI evidence; browser theme as an optional bonus

Bracketed text is a stage direction, not part of the spoken script. Presenter A
and Presenter B are speaking roles, not claims about individual contributions.
Agree on the split before presenting. Use only fictional demonstration accounts.

## Before the audience arrives

- Confirm the instructor's required format, time allowance and complete rubric.
- Use the latest reviewed main revision. Do not introduce untested code just
  before the demonstration. Restart any old app/web process after updating.
- Verify Python 3.11+, Tk and dependencies on the actual presentation computer.
  The desktop requires at least a 1000 × 740 window; check projector scaling.
- Close personal accounts and password managers. Disable unrelated notifications.
- Prepare a new `demo-data` folder and choose `demo-data/demo.vault` in the native
  save dialog. If that file already exists, choose a NEW filename; do not overwrite it.
- Use the synthetic passphrase `rehearsal only synthetic master`, label
  `School demo`, and username `student.demo`. These are public test fixtures,
  never real credentials. Generate the entry password inside Hakimino.
- Have the README architecture section, terminal, and matching CI page ready.
- Run the checks below before presenting, not while the instructor waits:

macOS / Linux, from the project root:

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install ".[test]"
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q -rs
node --test tests/web_reveal.test.cjs
.venv/bin/python -m hakimino.gui
```

Windows PowerShell uses `python -m venv .venv`, then
`.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Node is needed for frontend tests, not to run the desktop application.

## 1. Introduction — about 45 seconds

[Presenter A. Show the application and README project title.]

“Hello. We are presenting Hakimino, our local encrypted password manager for
Project 2. It stores account credentials in an encrypted file on the user's
computer. The cat-themed interface is our usability addition; the core of the
project is the security design underneath it.

We will demonstrate four requirements: Argon2id processing of a master
passphrase, derivation of an encryption key, authenticated vault storage with
AES-GCM, and random password generation using Python's secrets module.
Everything shown today uses synthetic demonstration data.”

## 2. Create and save — about 90 seconds

[Enter the synthetic master passphrase, click Create, repeat it in the confirmation
dialog, and choose a new `.vault` filename. Add `School demo` / `student.demo`.
Generate a 24-character password and save the entry.]

“I will first create a new vault. Creation requires a master passphrase of at
least twelve characters and asks me to confirm it. An existing vault is never
silently overwritten.

Now I will add a fictional school account. The password generator uses
`secrets.choice`, rather than the ordinary random module. Its default length is
twenty-four characters, with an allowed range of sixteen to one hundred and
twenty-eight. Each character is sampled from our configured alphabet.

After I click Save, the record is persisted to the encrypted vault. This is not
just a browser mock-up or an in-memory list. The desktop and CLI use the same
storage module and the same encrypted file format.”

[Search for `school`; then search for `missing`; clear the search and select the
record again.]

“The search makes the saved entry easy to find. A non-matching search shows an
empty result, and changing the selection clears the previous details.”

## 3. Show, hide and explain the cryptography — about 2 minutes

[Select the entry. Show that the password starts masked. Click Reveal. Explain
the first paragraph while the real fifteen-second timer runs; then point out
that the password is masked again. Do not photograph a revealed password.]

“Passwords are hidden by default. Revealing one is an explicit action, and it
is hidden again after fifteen seconds. The application also locks after five
minutes of inactivity. We checked both default intervals during our rehearsal,
without shortening their timers.

The master passphrase is combined with a random sixteen-byte salt and processed
by Argon2id. Our chosen profile uses sixty-four mebibytes of memory, three
iterations, and one lane. Argon2id makes offline guessing more expensive; it does
not make a weak passphrase impossible to guess.

The result is a thirty-two-byte key for AES-256-GCM. We do not save that key or
a separate password verifier to disk. AES-GCM encrypts the entry collection and
authenticates it. The header is authenticated as additional data.

Every save uses a fresh salt and a fresh twelve-byte nonce. The salt is used in
key derivation; the nonce is used by GCM. They have different jobs, and neither
needs to be secret. The saved file contains public metadata and ciphertext with
an authentication tag, not the plaintext account collection.”

[Show the README data-flow diagram. Do not claim that merely looking at an
unreadable file proves the encryption is secure.]

## 4. Lock, reject a wrong password and restart — about 90 seconds

[Click Lock. Enter an intentionally incorrect passphrase and attempt Unlock.
Show the error without exposing any records. Then enter the correct passphrase.
Close the app, relaunch it, browse to the same vault, and unlock again.]

“Locking clears the displayed entry fields and releases the session's reference
to the master passphrase. An incorrect passphrase is rejected, and the failed
attempt does not modify the vault.

The same generic authentication error can mean a wrong passphrase or a damaged
vault. We do not pretend to distinguish those cases just from an invalid tag.

After restarting the application, the correct passphrase restores the saved
record. This demonstrates persistence across application processes, rather than
only within the current window.”

## 5. Safe failure paths and stale deletion — about 90 seconds

[Presenter B. Click Delete on the synthetic record and cancel. Show it remains.
Use the test evidence for tampering and concurrency; avoid improvising file
corruption or multi-client timing on stage.]

“Cancelling deletion leaves the file unchanged. We also test authentication
failure after modifying ciphertext in a disposable copy. AES-GCM rejects that
copy, and the original vault remains untouched.

During review we found a concurrency problem: an old view could delete a new
entry if another client deleted and recreated the same label. We fixed that
across the desktop, CLI and local web interface.

Deletion now carries the revision of the encrypted vault that the user saw.
The storage layer authenticates the file, compares that revision and performs
the write while holding the same file lock. If the file changed, deletion is
refused rather than applied to a replacement. Even recreating identical entry
contents changes the ciphertext revision.

This check is deliberately conservative. A change to an unrelated entry also
requires a fresh view before deletion. It prevents stale cooperative operations;
it is not a defense against someone maliciously restoring an older valid file.”

[Optional focused regression commands. Windows: substitute the virtualenv Python
path as described above. These tests create disposable data automatically.]

```sh
.venv/bin/python -m pytest -q tests/test_vault.py -k 'tampering or stale or revision'
.venv/bin/python -m pytest -q tests/test_gui.py -k stale
.venv/bin/python -m pytest -q tests/test_web.py -k 'stale or revision'
```

## 6. CLI, verification and conclusion — about 90 seconds

[With the GUI locked, run the CLI against the exact demonstration file. Replace
the path if the native save dialog selected a different location.]

```sh
.venv/bin/python -m hakimino --vault demo-data/demo.vault list
.venv/bin/python -m hakimino --vault demo-data/demo.vault show "School demo"
```

“The CLI prompts for the master passphrase without echoing it. By default,
showing an entry prints its username but keeps the password hidden. Revealing
it requires an explicit option; we do not need that option for this demonstration.

For the final web-polish version, the full suite passes ninety-three Python tests
and thirty-one frontend tests, with no skips. Dependency checks also pass. Our GitHub
CI runs on Python 3.11 and 3.12 with a working Tk display.
[Show the successful run for the exact submitted commit before presenting it
as remote verification.]
We additionally exercised twelve CLI scenarios using real terminal processes.

This remains a coursework prototype. An unlocked process contains secrets in
memory, Python does not guarantee secure memory erasure, and we do not claim
protection against a compromised operating system. There is no recovery feature
for a forgotten master passphrase. The optional local web demo shares unlock
state and is not designed for public hosting or real multi-user accounts.

In summary, Hakimino combines the four required security mechanisms with local
persistence, explicit failure handling and a themed interface. Thank you. We are
ready for your questions.”

## Optional UI bonus — 30 seconds, only if time permits

[Open the separately started local web demo with synthetic data only.]

“The browser theme is an optional presentation layer over the same vault
storage. It uses bundled images and different error illustrations. It is not a
cloud password manager and does not add an external database.”

Do not select Preview critical error without explaining it: it is a **simulated
visual error**, and it really locks the local web session. After lock or a failed
unlock, the current page retains the filename but clears the master passphrase.
A full page reload starts with the default filename again; this convenience
does not store credentials in browser storage. The count uses “1 entry” and
“0 entries” / “2 entries” correctly.

## Likely questions — concise answers

**Why Argon2id instead of SHA-256 for the master password?**
SHA-256 alone is designed to be fast. Argon2id is a password-based, memory-hard
key derivation function. Its work and memory costs slow repeated guesses.

**What is the difference between hashing and encryption here?**
Argon2id derives key material from the passphrase and salt. AES-GCM is reversible
with the correct key and authenticates the encrypted records. The SHA-256 digest
used for concurrency is of ciphertext, not of the user's master passphrase.

**Why use AES-GCM rather than encryption without authentication?**
We need confidentiality and rejection of unauthorized changes, not just unreadable
bytes. GCM provides an authentication tag as well as encryption.

**Does GCM detect every possible file change?**
No. It authenticates the protected header values and ciphertext. JSON formatting
changes and replay of a complete older valid vault are not the same as ciphertext
tampering; we do not claim rollback protection.

**Does every generated password contain all character classes?**
No. Sampling is uniform from the combined alphabet. The implementation does not
force at least one character from each class. Length and unpredictability are
our stated generator properties.

**Where is the database?**
Persistence is the local encrypted `.vault` file, not an SQL database. The
interfaces share the same storage and cryptographic implementation.

**Can you recover a forgotten master passphrase?**
No. There is no stored recovery key or recovery service. Keep the passphrase and
appropriate encrypted backups safe.

**What did each teammate implement?**
[Answer using the contribution split agreed by both teammates. Do not invent
ownership or claim that an AI-assisted review was a human teammate's review.]

## Recovery plan if a live step fails

- Check the filename, selected Python environment and passphrase first. Do not
  delete a vault, disable authentication or overwrite an existing file to hurry.
- For a stale-view warning, unlock again and review the current record.
- If native Tk cannot start on the presentation machine, use the rehearsed CLI
  and explain the GUI limitation honestly. Ask whether the instructor accepts
  that fallback; the optional browser is not automatically an equivalent rubric item.
- If time is short, omit the optional web theme and focused test reruns. Keep
  creation, encrypted persistence, generation, lock/unlock and the security explanation.
- The full five-minute idle interval is best demonstrated before the talk or on
  request. Do not silently shorten it and call that the default behavior.
