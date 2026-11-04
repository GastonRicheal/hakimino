# Acceptance status — 4 November 2026

## Scope

Application baseline: `7e7e35308ae557351a6a2232f2e6ee5a5cfc67f7`.
Environment: macOS 26.4 arm64, Python 3.12.14, isolated project virtualenv.
No application source changes. All credentials are explicitly synthetic.
No real vaults or user credentials were read or submitted.

**This record distinguishes process-level automation from manual GUI acceptance.**
The CLI was exercised using real fresh processes and real terminal prompts, driven
by a script. It is not a claim that a human manually typed each command.

## CLI process acceptance: PASS

Command:

```sh
.venv/bin/python scripts/verify_cli.py
```

Actual result: exit 0, 12 checks passed; temporary vaults removed automatically.
The driver uses Python standard-library POSIX pseudo-terminals, without patching
application functions, input, or password prompts. It has per-process timeouts,
checks exit codes and output, and kills unfinished child processes on failure.
It outputs only check names and status, never captured passwords or transcripts.

| Check | Result |
|---|---|
| Create a vault with master-password confirmation and no prompt echo | PASS |
| Add an entry through real password prompts without echo | PASS |
| List persisted entries from a fresh CLI process | PASS |
| Show username while keeping the password hidden by default | PASS |
| Reveal password only with the explicit flag | PASS |
| Reject a wrong master password and preserve original file bytes | PASS |
| Refuse to initialize over an existing vault | PASS |
| Cancel deletion and preserve original file bytes | PASS |
| Generate, save, and retrieve a 24-character password | PASS |
| Confirm deletion and verify absence from a fresh process | PASS |
| Reject a ciphertext-modified disposable copy without changing it | PASS |
| Check stored test values are not plaintext and locks/temp files are cleaned up | PASS |

Substring checks are smoke checks, not proofs of cryptographic security. The
existing unit tests provide additional functional and rejection coverage.
The PTY driver requires POSIX; it is not a verified Windows acceptance driver.

## Native GUI manual acceptance: BLOCKED / NOT COMPLETED

The GUI process was launched, but the desktop-control inventory did not expose a
selectable Python/Hakimino window. A direct Python app selection timed out. No
native clicks, visual screenshots, or manual GUI outcomes are claimed here.
Existing Tk widget tests are separate automated evidence, not a replacement for
human usability checks. Full-length 15-second reveal and five-minute idle timing
have not been manually verified.

## Team manual checklist

Both teammates should execute this checklist using only disposable synthetic
credentials. Record the actual OS, Python/Tk versions, source commit, tester,
date, result, and evidence. Leave unchecked items pending; do not infer success
from the other teammate's environment.

- [ ] Install from a clean checkout and launch the GUI without errors.
- [ ] Create a disposable vault, including the native confirmation/save dialogs.
- [ ] Add an entry and generate a password; confirm it stays masked.
- [ ] Search for matching/nonmatching entries and check field clearing.
- [ ] Reveal a password; wait the full 15 seconds and confirm it hides again.
- [ ] Lock manually; confirm displayed secrets clear and unlock is required.
- [ ] Close the application, relaunch, browse to the vault, and confirm persistence.
- [ ] Enter a wrong master password; confirm no records are revealed.
- [ ] Cancel deletion, then confirm deletion of a disposable entry.
- [ ] Unlock, leave untouched for five full minutes, and confirm automatic locking.
- [ ] Check text, buttons, layout, focus, and window resizing on the actual screen.
- [ ] Confirm CLI creation/list/show/delete behavior on the second machine.

| Tester / machine | Native GUI checklist | Evidence |
|---|---|---|
| Current Mac, agent desktop-control attempt | BLOCKED; not completed | App selection unavailable/timeout |
| First teammate, manual session | PENDING | Not supplied |
| Second teammate, actual machine | PENDING | Not supplied |

Use masked synthetic records in screenshots. Never upload a real password vault,
master password, or private account data. Submission readiness remains pending
manual team checks and the final README review; this report is not an instructor
acceptance or a production security certification.
