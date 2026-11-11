# Defensive security review and remediation — 11 November 2026

## Scope and conclusion

Baseline reviewed: `ed49da36acbe3258074f199fee58eb8da81a4214` on `main`.
This report accompanies the subsequent security-fix commit; its exact identity
is the Git commit containing this file, not the baseline SHA above. Confirm its
own GitHub Actions run before treating local results as remote verification.

**Confirmed issues were fixed, with regression tests. This is not a certification
that the project is unbreakable or free of unknown vulnerabilities.** The review
covered `hakimino/vault.py`, `session.py`, `cli.py`, `gui.py`, the local HTTP server,
shipped JavaScript, tests, packaging metadata, dependencies and CI configuration.
All live checks used disposable synthetic vaults and local loopback services.
No external service was attacked, and no real vault or credential was read.

The main confirmed confidentiality issue was the optional web demo's previously
documented process-wide unlock state. It was **not an AES-GCM/Argon2 break** and
was not a demonstrated Internet attack. Desktop/CLI did not share that web state.
The shared-session limitation is now narrowed to tabs sharing one browser cookie.

## Findings, fixes and reproducible regression evidence

### 1. Independent local clients inherited an unlocked web vault — confidentiality

**Condition and effect:** while one browser had a vault open, a fresh independent
client could GET the app, receive the same cookie/CSRF values, and reveal that
vault's synthetic entry without supplying its master passphrase. This was
reproduced against the baseline. A local client could also manipulate the shared
session. The documented synthetic-only scope reduced real-world exposure but
was not an adequate isolation boundary for independent clients.

**Fix:** `hakimino/web.py:29–90`, `92–131`, `205–214`, `239–270` now allocate
random cookie/CSRF credentials and a distinct `BrowserState`/`VaultSession` per
client. A new client starts locked. A client's wrong password, explicit lock or
idle expiry does not lock another client's session. Same-cookie refresh retains
only that cookie's context. Host, Origin and cookie-bound CSRF checks remain.

**Tests:** `test_independent_browser_cannot_inherit_unlocked_vault`,
`test_cookie_and_csrf_are_bound_to_same_browser`,
`test_browser_idle_lock_is_independent`. The independent client is denied reveal
and deletion even when the test supplies the owner's epoch/revision. Correct
master authentication is required before that client can read the same vault.
Existing stale-view tests still reject cross-unlock and same-name-replacement
operations without revealing or rewriting data.

**Delivery impact:** fixed before this security delivery. No migration or change
to the desktop/CLI cryptographic format is needed.

### 2. Malformed inputs caused uncontrolled failures — availability/robustness

**Condition and effect:** a JSON list used as an action triggered a TypeError,
HTTP 500 and the old shared-session lock. An unpaired Unicode surrogate in a
master password raised an uncontrolled UnicodeEncodeError. Both were reproduced.
This did not demonstrate decryption or permanent data loss. Authenticated local
requests, rather than an external unauthenticated attack, are the relevant scope.

**Fix:** `hakimino/web.py:40–44`, `225–270` validate action types, bounded HTTP
framing and strict JSON (including duplicate keys and non-finite numbers).
`hakimino/vault.py:75–105` rejects invalid Unicode with safe `VaultError` messages.
Malformed JSON/action/entry data leaves existing ciphertext unchanged and does
not unnecessarily lock the caller. An attempted unlock/create still intentionally
locks that client's previous session before validating the new credentials.
Unexpected failures lock only the affected client's session and do not return
internal exception details.

**Tests:** invalid-action parameter cases, malformed-JSON cases, invalid-Unicode
master/label/username/password cases, existing validation-preservation and
unexpected-failure tests. These assert controlled errors and unchanged files.
Framing checks were also reviewed statically; not every HTTP parser combination
was independently fuzzed.

**Delivery impact:** fixed; these are controlled failure-path improvements, not
claims of a remote code execution vulnerability.

### 3. Special-file blocking and final-path symlink race — local hardening

**Condition and effect:** opening an attacker-prepared FIFO as a vault could block
before the bounded read; a final-component symlink swap could bypass the earlier
path check. Both require local filesystem influence. This does not grant master
password knowledge or defeat ciphertext authentication. The pre-fix FIFO hang was
identified statically, not executed against a user's working application.

**Fix:** `hakimino/vault.py:173–188` uses nonblocking/no-follow open flags where
available, then verifies the opened descriptor is a regular file and checks its
size before a bounded read. The opened descriptor, not just the path, is checked.

**Tests:** `test_nonregular_vault_is_rejected_without_blocking` uses a disposable
POSIX FIFO and a three-second subprocess timeout; `test_final_component_symlink_race_is_rejected`
simulates a final-path swap inside a temporary directory and checks that the
target and lock cleanup are preserved. macOS and Linux expose the tested flags.
Platforms without `O_NOFOLLOW` retain the ordinary symlink check but do not get
that extra race protection. The Windows FIFO alternative checks a directory,
not FIFO behavior; Windows was not rerun in this follow-up.

**Delivery impact:** fixed on the verified platforms. Hostile replacement of
parent directories, alternate path aliases and operating-system compromise
remain outside this application's security boundary.

### 4. Bound local HTTP resources — defense in depth

`hakimino/web.py:22–26`, `108–155` limits browser contexts to 32 and concurrent
request workers to eight, expires inactive contexts after one hour and applies a
five-second socket read-idle timeout (including headers). Secret sessions still
lock after five minutes without an operation; status polling does not extend
that secret lifetime. Capacity/expiry and an idle-header socket are regression
tested with short test timeouts. These limits are **not an absolute request
deadline and do not guarantee denial-of-service resistance**. Local clients can
still occupy capacity; this remains a local development server.

## Other reviewed controls and limits of the evidence

- Argon2id remains version 19, 64 MiB, three iterations, one lane and a 32-byte
  derived key. The complete KDF profile is pinned before derivation, so a vault
  cannot request arbitrary KDF costs. Fresh 16-byte salts and 12-byte nonces are
  generated with `secrets`; AES-GCM authenticates canonical metadata and entries.
- Existing tests cover wrong masters, tampering, atomic-write failure handling,
  no overwrite on creation, ciphertext revision checks under the same file lock,
  stale deletion, locked access and native Tk workflows. Password generation uses
  `secrets.choice`. No replacement cryptographic primitive was introduced.
- Frontend review found user-controlled values escaped before HTML insertion and
  revealed passwords assigned through `textContent`. Existing 31 frontend tests
  cover hiding and delayed-response privacy. No browser credential storage,
  external analytics or new plaintext response path was introduced.
- Source enumeration found no tracked `.vault`, `.env`, virtual-environment,
  private-key file or credential file in the reviewed delivery. This is not an
  exhaustive forensic scan of every historical Git object or untracked file.
  The pre-existing untracked `build/` directory was not staged or removed.
- CI uses read-only repository permissions and commit-pinned checkout/setup
  actions. This review does not certify the entire upstream supply chain.

## Test and scanner results

Evidence is stored in [security evidence](security-evidence-2026-11-11/).

| Evidence | Actual result and interpretation |
| --- | --- |
| Baseline synthetic isolation/input checks | Inherited reveal reproduced; malformed action locked shared session; invalid Unicode produced an uncontrolled exception. |
| Local `python -m pytest -q -rs` | **116 passed, no skips**, macOS arm64 / Python 3.12.14, including real Tk widget tests. |
| Targeted vault/web suite | **93 passed** before the final test-expression cleanup. |
| `node --test tests/web_reveal.test.cjs` | **31 passed, no skips**, Node 24.21.0; simulated DOM/controlled network timing, not a new full-browser visual rehearsal. |
| `python -m pip check` | **No broken requirements found.** |
| Fresh install | Only tracked candidate files copied to a temporary source directory; installed non-editably into a new virtual environment. Installed CLI entry points and all 11 bundled PNG assets checked. |
| Installed-package test isolation | **116 passed, no skips**; see `installed-pytest.log`. Run from outside the source tree with `--import-mode=importlib`, after verifying imports resolve to site-packages. |
| Bandit 1.9.4, application Python files | One low-severity B105 at `hakimino/cli.py:59`: the literal `[hidden; use --reveal]`. Manually reviewed as a masking placeholder, not an embedded credential. No other reported findings; a clean scanner is not proof of safety. |
| pip-audit 2.10.1 | No known vulnerabilities reported for the five exact installed runtime package versions in `runtime-requirements.txt`; only public package names/versions were submitted to the advisory service. This does not cover future releases or unknown vulnerabilities. |
| Remote CI | Verify the matching security-fix SHA in Actions after push. Older green runs do not validate these changes. |

The runtime versions audited were argon2-cffi 25.1.0, argon2-cffi-bindings 26.1.0,
cryptography 50.0.2, cffi 2.1.1 and pycparser 3.12. No dependency upgrades were
required by this result. Full OS/browser interaction, a fresh Windows run and
another real five-minute wall-clock rehearsal were not performed in this audit;
the earlier rehearsal remains historical evidence, not a new result.

## Remaining risks and acceptance advice

1. A copied vault can be guessed offline. Use a strong unique master passphrase;
   Argon2 makes guesses more expensive but cannot make weak passwords safe.
2. Compromised OS/browser, local malware, keyloggers and stolen session cookies
   are outside the boundary. Python does not guarantee secure memory erasure.
3. Same-profile tabs share cookies and unlock state. Cookie names distinguish
   app ports but cookies are not a port-isolated defense against malicious local
   applications. This is not real multi-user authentication/authorization.
4. No TLS or public-hosting support. Keep the web server on loopback and use only
   synthetic demonstration data. Python's own documentation warns that
   [http.server is not recommended for production](https://docs.python.org/3/library/http.server.html).
5. Rollback of a previously valid vault is not detected. File locks coordinate
   cooperating clients, not hostile filesystem writers. Keep encrypted backups;
   backups can contain deleted entries. Forgotten masters cannot be recovered.
6. The full Project 2 rubric still needs human confirmation. Check the acceptance
   computer's native dialogs, display, Python/Tk installation, teammate details
   and actual submission destination before the deadline. Test success is not
   evidence that the coursework has been submitted or guaranteed full marks.

The recommended acceptance path remains desktop/CLI with disposable data; the
local themed web UI is an optional demonstration. Do not advertise this coursework
prototype as a production password manager or claim it cannot be compromised.
