# Local web UI

This optional interface exercises the real `VaultSession` and encrypted `.vault` file storage. It is not a static mockup, SQL database, cloud service, or replacement for the desktop app. UI copy is English; the brand is Hakimino.

## Run

From the repository with dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m hakimino.web --port 8766 --data-dir ./vaults/web-tests
```

On macOS or Linux:

```sh
.venv/bin/python -m hakimino.web --port 8766 --data-dir ./vaults/web-tests
```

Open the printed loopback address in a browser. Use a dedicated test vault and test credentials. Create `ui-test.vault` with a passphrase of at least 12 characters. Add an entry, lock, refresh, unlock with the same passphrase, and verify the saved entry. Delete requires confirmation. Existing vaults are never overwritten by creation.

Data is saved to the selected directory as Argon2id-derived AES-GCM ciphertext using the existing atomic write and file-lock implementation. Master passphrases are retained only in the Python session while unlocked; Python does not guarantee secure memory erasure. The web UI does not use localStorage or sessionStorage. Passwords are sent over loopback HTTP, returned only on reveal, and hidden after 15 seconds or when the page is hidden. Closing a tab does not immediately terminate the server session; it expires after five minutes without an operation. Reloading the app while unlocked resumes that local session. Tabs connected to the same server share the session.

Opening or reopening a vault invalidates previous views. If another tab changes
the open vault, operations from the old view are refused and the old view clears
when it next checks the session. Unlock the intended vault before continuing.

## Same-vault stale-view protection

The unlock epoch still protects against views from an earlier unlock. A separate
`vault_revision` now binds each read/reveal or delete request to the ciphertext
seen by that browser. Missing or stale revisions are rejected with HTTP 409;
no entry contents are returned and no write occurs. Status returns labels and
revision from one authenticated, locked snapshot. It must not authorize another
tab's old selection. Periodic status checks clear a changed view instead of
silently updating its revision while preserving the old selected entry.

The same storage-level check protects desktop and CLI deletion. It is vault-wide,
so even an unrelated save can require unlocking and reviewing again. All clients
must run the updated code; this is not a malicious-rollback defense. The server's
shared unlock state remains a documented local-demo limitation. Use synthetic data
only. See [regression evidence](verification/stale-deletion-fix-2026-11-11.md).

## Scope and safeguards

- Bind only to `127.0.0.1`; do not proxy, expose, or deploy this development server publicly.
- Exact Host and Origin checks, a per-process CSRF token and an HttpOnly SameSite cookie guard API calls. These do not protect against malicious software running as the same local user.
- Only bundled HTML, JavaScript and PNG assets are served. Vault paths cannot be selected outside the configured directory.
- No credential or request-body logging; no cache, external scripts, third-party fonts or analytics.
- Server sessions expire after five minutes of API inactivity; background status polling does not extend expiry.
- Expected validation errors show the facepalm cat; access failures show the surprised cat; unexpected server errors lock the session and show the hissing cat without returning exception details.
- “Preview critical error” is explicitly a simulation: it really locks the session, leaves persisted entries unchanged and opens the error UI. It does not crash the server.
- Stop the process with Ctrl+C to release the session. Encrypted vault files remain for later testing; no automatic deletion occurs.

## Validation

`tests/test_web.py` uses a temporary directory and real HTTP requests to verify creation, encrypted persistence, generation, reveal, lock/unlock, deletion, unchanged files after failed operations, path restrictions, request-origin checks and fail-closed unexpected errors. The test does not use production credentials.

Run `node --test tests/web_reveal.test.cjs` with Node.js 18+ to check frontend
reveal timing. Hide, page visibility changes, navigation and lock invalidate
outstanding reveal replies. Returning to a tab requires a new explicit reveal;
a late response must not restore plaintext. Hide remains usable while a reveal
request is pending. The tests execute the shipped JavaScript against a minimal
DOM with controlled network timing, rather than claiming a full-browser test.
