# Project 2 submission handoff

The desktop and command-line applications cover the four requirements shown in
*Class 7 NotesApp Login Fix*, PDF page 16. The [README](../README.md) maps those
requirements to the implementation and explains the security choices. The slide
gives a 12 November deadline. Confirm the exact cutoff, submission destination,
and accepted files or links using the full Project 2 instructions on the course site.

## Coursework delivery scope

Use the desktop application for the live demonstration and the CLI for the
terminal workflow. The optional browser interface is a local demonstration
surface for synthetic data. Browser clients connected to one server process
share its unlock state. The desktop and CLI use the same encrypted file format.

## Integrated delivery status — 11 November 2026

[PR #7](https://github.com/GastonRicheal/hakimino/pull/7) is merged. The verified
application revision on `main` is `f2d664226c67aa4abc1d18633a7c53664d0dfc71`.
Its tree is identical to reviewed candidate `07f071ac825c88674c50c9f52a0fe6fc2d8f9181`.
The [main CI run 43046115283](https://github.com/GastonRicheal/hakimino/actions/runs/43046115283)
passed on both Linux/Python versions: 74 Python tests, 13 frontend tests and
`pip check`, with no skipped tests. The repository was confirmed public with
`main` as its default branch; instructor receipt has not been established.

See the [final verification record](verification/submission-2026-11-11.md) for
clean-install evidence, archive checks, limitations and a submission checklist.
Later documentation-only commits must still be checked against their own CI;
the linked run above applies specifically to `f2d6642`.

## Previously recorded Windows rehearsal — 11 November 2026

Implementation commit [`8716ab2`](https://github.com/GastonRicheal/hakimino/commit/8716ab217e03d5feb5a88560d8f3503d6fe3cd5e)
was installed from its Git source archive in a fresh Windows virtual environment.
All 74 Python cases and 13 frontend cases passed without skips, and both Linux
jobs passed in [CI run 43032076610](https://github.com/GastonRicheal/hakimino/actions/runs/43032076610).

The scripted demonstration drove the Tk interface from the checkout with a
disposable vault and supplied responses to the creation dialogs. It created
the vault, generated and saved a 24-character password,
searched for the entry, and verified that the password hid after the default
15-second interval. It then locked the vault, rejected a wrong master password,
and recovered the saved entry after the correct one was entered. A separate
real-duration Tk check confirmed the five-minute idle lock and field clearing.

This Windows rehearsal is the team's prior record, not a newly repeated test
in the final macOS review. The final review independently confirmed a real
15-second Tk reveal interval but did not repeat a full five-minute idle wait.
Application and test files are unchanged between `8716ab2`, reviewed `07f071a`
and the integrated `f2d6642` tree.

## Verify the candidate

Use the agreed GitHub revision or extract the corresponding source archive to
a new directory. Open a terminal in the directory containing `pyproject.toml`.
The source archive contains the README, code, bundled UI assets, and tests.

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[test]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q -rs
node --test tests/web_reveal.test.cjs
.\.venv\Scripts\python.exe -m hakimino.gui
```

On macOS/Linux, use `python3` and `.venv/bin/python` in the corresponding
commands. Tk and a display are required for desktop verification. Node.js is
required only for the frontend regression suite. Check the matching revision in
the [GitHub Actions results](https://github.com/GastonRicheal/hakimino/actions).

## Demonstrate with a disposable vault

Use synthetic data and the updated application in every client. Stale deletion
is now rejected by a ciphertext-revision check under the file lock, including
same-name replacements with identical contents. If another client saves, unlock
again and review before retrying; no data is changed by the rejected deletion.
The web interface still shares its local server session. See the
[follow-up fix and tests](verification/stale-deletion-fix-2026-11-11.md).

1. Create `demo.vault` with a synthetic master passphrase. Add an entry using a
   fictional username and generate its password in the app.
2. Save, search for the entry, and show that the password is masked. Reveal it,
   then hide it again or let the 15-second timer expire.
3. Lock and reopen the vault. A wrong passphrase must fail. The correct one
   should restore the saved entry, including after a restart.
4. Explain how Argon2id and a salt derive the key, how AES-GCM uses a nonce and
   authentication tag to reject changes, and how `secrets` samples passwords.
   Use the [README encryption flow](../README.md#architecture-and-encryption-flow).

## Before submission

- Review the source and test results for the exact revision to be submitted.
- Confirm both names and student IDs in the README. Record individual work only
  after both teammates agree on the wording.
- Obtain teammate review for any open PR before merging, as agreed in
  [WORK_PLAN.md](../WORK_PLAN.md).
- Confirm the requested submission format on the course site, then submit the
  agreed revision or matching archive and keep the submission confirmation.

Keep generated vaults and private credentials out of the submission. Use the
[manual team checklist](verification/acceptance-2026-11-04.md#team-manual-checklist)
to record any demonstrations performed by the two teammates.
