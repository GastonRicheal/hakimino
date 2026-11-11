# Stale deletion fix — 11 November 2026

## Scope

Follow-up to application merge `f2d6642` and documentation revision `a357fd9`.
The stale same-name deletion reported in the earlier review is fixed across the
desktop, CLI and optional local web interface. This is a targeted correction,
not a claim of a defect-free or production-certified password manager.

## Root cause and correction

Previously, a confirmed deletion reloaded the current file and deleted by label
alone. Another client could delete and recreate that label between viewing and
confirmation; the old client then deleted the new record.

The correction uses an authenticated ciphertext snapshot and its SHA-256 digest
as a vault-wide revision. `operate(..., "snapshot")` returns labels and revision
from the same locked read. `delete` requires `expected_revision`; authentication,
comparison and mutation take place under the same existing file lock. Failed
comparison never reaches the write operation. This digest is not a password
verifier, a derived encryption key or a new on-disk format.

- Desktop: capture the selected view's revision before the confirmation dialog.
  A conflict locks the session and clears entry details, including revealed text.
- CLI: authenticate and snapshot before prompting for `DELETE`; compare after
  confirmation. A conflict exits with status 1 without changing the vault.
- Web: require the requesting browser's `vault_revision` for show/reveal/delete,
  separately from `vault_epoch`. Missing or stale versions receive HTTP 409 with
  no entry fields. Another browser's status request cannot authorize an old view.
  Polling invalidates changed views; in-flight reveals retain generation guards.
- Existing version-1 vaults remain readable without migration. Freshly reviewed
  entries can still be deleted through every interface.

## Executed verification

A fresh directory containing only the tracked source files (including this fix)
was used to create a new Python 3.12.14 virtual environment on macOS. No personal
vaults or credentials were used. Non-editable installation was exercised.

| Command / check | Observed result |
| --- | --- |
| `python -m pip install ".[test]"` | Successful clean installation |
| `python -m pytest -q -rs` | **93 passed**, no skips, 69.85 seconds; includes real Tk widgets |
| `node --test tests/web_reveal.test.cjs` | **18 passed**, no failures or skips, Node 24.21.0 |
| `python -m pip check` | No broken requirements found |
| Installed package outside the source directory | Confirmed imports from site-packages, revision-aware web resource and all 11 PNG assets |
| Installed-package two-session smoke test | Identical-content same-name replacement survived a rejected stale deletion |
| Installed CLI entry points | Both `python -m hakimino --help` and `hakimino --help` succeeded |
| `git diff --check` | Passed before commit |

The first development run exposed a locked-web-request status regression
(409 instead of the existing 400 response). This was corrected without weakening
the test; the complete final run above passed. The new frontend tests use the
existing controlled minimal DOM, not a full real-browser automation suite.

Regression coverage includes different and identical replacement content,
missing/invalid revisions, no-write-on-conflict byte comparison, lock-held read
and write, unrelated entry saves, desktop confirmation-time changes, CLI
confirmation-time changes, external CLI/session and second-tab web mutations,
stale reveal rejection, polling invalidation and fresh-view recovery.

The corresponding GitHub CI must be checked for the exact pushed commit; local
results above are not a substitute for that run. The workflow runs Python 3.11
and 3.12 with Tk/Xvfb and the frontend suite. See
[the main-branch Actions runs](https://github.com/GastonRicheal/hakimino/actions?query=branch%3Amain).

## Boundaries and rehearsal

This is conservative, vault-wide optimistic concurrency control: an unrelated
save also invalidates a pending deletion. Unlock again and review the current
entry before retrying. Run the updated version in all clients; old binaries that
omit this check must not be used concurrently. Restart the local web server and
reload the browser after updating so both backend and frontend use this fix.

The check does not prevent malicious restoration of an older encrypted file,
non-cooperating direct writes or path aliases bypassing the lock. The optional
web server still shares unlock state across local browser clients and is only
for synthetic local demonstrations. These boundaries are unchanged.

The team must still rehearse on the actual acceptance machine, confirm the full
course brief and submit through the instructor's required channel. A green CI
or this corrective commit is not evidence of course submission or a perfect
project.
