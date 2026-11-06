# Project 2 delivery checklist

Baseline reviewed: `7e7e353`. Plan created: 4 November 2026.
Status refreshed: 6 November 2026, after PRs #1–#6 merged into `cfa0470`.
Historical baseline reports remain tied to the exact revisions they tested.
This is a proposed team work plan, not a claim that optional features are required
by the instructor. Agree on ownership with the other contributor before parallel work.

## Workflow

One scoped task per branch and pull request. Each change includes its tests and
relevant documentation. Do not push directly to main or merge without teammate
review. Record actual results, including skipped tests; never claim unrun tests pass.
Use synthetic credentials only. Never commit vault files, secrets, or private reports.

## Ordered work

- [x] 0. Record this checklist and the review baseline.
- [x] 1. Establish a reproducible local baseline.
  - Install the project and test dependencies in an isolated environment.
  - Run the existing suite; record OS, Python/dependency versions, commit, and
    passed/failed/skipped counts. Separate unavailable GUI support from test success.
  - Deliverable: verification record; address discovered failures in separate fixes.
  - Evidence: `docs/verification/baseline-2026-11-04.md` (46 tests on macOS);
    integrated `cfa0470` also passed 69 tests without skips on Windows on 6 November.
- [x] 2. Add continuous integration for existing tests.
  - Run core and real Tk widget tests with a suitable display (for example Xvfb
    on Linux). Report skips explicitly. Do not execute real vault operations in CI.
  - Acceptance: CI runs on pull requests and its first actual result is recorded.
  - Evidence: PR #3 merged; Actions run `41882203499` passed on integrated main.
- [ ] 3. Validate the GUI and CLI end to end on team machines.
  - Create, add, generate, search, reveal/hide, delete/cancel, lock, and reopen.
  - Check wrong-password handling and tampering rejection using disposable copies.
  - Check inactivity locking and persistence after restart.
  - Acceptance: real results and synthetic-data screenshots; each teammate records
    their own machine results. Automated checks do not replace manual usability review.
- [ ] 4. Add editing of existing entries (proposed improvement, pending team agreement).
  - Shared storage operation first, then CLI/session/GUI support without duplicated crypto.
  - Define rename/collision semantics; preserve originals on cancellation or failure.
  - Acceptance: edit/reopen, invalid-input, collision, locked-session, and write-failure
    tests; updated usage documentation. Split implementation into focused PRs if needed.
- [x] 5. Strengthen the explanation and evidence in the README.
  - Add a master-passphrase -> Argon2id -> key -> AES-GCM data-flow diagram.
  - Map confirmed requirements to code and tests. Explain salt, nonce, AAD,
    offline guessing, authenticated decryption, and memory/rollback limitations.
  - Link actual verification results; record only agreed, factual contributions.
  - Evidence: PR #5 merged with requirements mapping, encryption flow and dated results.
- [ ] 6. Freeze and rehearse the submission.
  - Install from a clean checkout and run tests on the exact candidate commit.
  - Rehearse a short synthetic-data demonstration; check team names/IDs together.
  - Confirm the instructor's submission channel, deadline time/timezone, and required
    files before delivering. A Git push is not proof of instructor receipt.

## Required external clarification

- [ ] Obtain the full Project 2 course-site brief and map every scoring item.
  The available Class 7 slide (PDF page 16, slide 09) specifies Argon2 master-password
  handling, a derived key, an AES-GCM vault, a Python secrets password generator,
  teams of 2–3, a 12 November deadline, and README worth half the project mark.
  The slide does not establish every parameter, feature, or submission detail.
- [ ] Agree task ownership with the other contributor and avoid overlapping edits.
- [ ] Confirm whether editing, master-password rotation, backup, or a separate
  verifier is required. Do not add these solely on the assumption they are mandatory.

## Out of scope unless required

Cloud sync, JWT/server login, MFA, automatic backup, and password rotation are not
currently scheduled. This checklist does not certify the application as production-safe.
