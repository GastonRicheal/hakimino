# Final technical submission check — 11 November 2026

## Scope and outcome

The integrated application is technically ready for a single-client Project 2
submission against the four confirmed requirements. This record does not certify
production security, unknown rubric items, instructor access from a particular
network, or successful submission to the course portal.

This is an AI-assisted verification record authorized by the project contributor.
It is not presented as an additional human teammate's independent sign-off.

## Revision and remote evidence

- Reviewed PR head: `07f071ac825c88674c50c9f52a0fe6fc2d8f9181`.
- [PR #7](https://github.com/GastonRicheal/hakimino/pull/7) merged into main as
  `f2d664226c67aa4abc1d18633a7c53664d0dfc71`.
- Git ancestry and tree comparison confirmed the remote merge contains the
  reviewed head and has an identical complete file tree.
- [Candidate CI 43037125765](https://github.com/GastonRicheal/hakimino/actions/runs/43037125765)
  tested merge preview `38fce7352120e7d69c795b695b7c839a4013f975` against base `cfa0470`.
- [Integrated main CI 43046115283](https://github.com/GastonRicheal/hakimino/actions/runs/43046115283)
  is a push run for `f2d6642`, not the earlier candidate run. Both job logs were read.
- GitHub reports the repository as public and `main` as the default branch.
- Documentation updates following this application revision do not extend old
  CI evidence to a new SHA. Check the successful run for the exact final commit
  via [GitHub Actions](https://github.com/GastonRicheal/hakimino/actions).

## Checks actually performed

| Check | Result and boundary |
| --- | --- |
| Fresh Git source archive and new macOS virtual environment | Non-editable `pip install ".[test]"` succeeded with Python 3.12.14 |
| `python -m pytest -q -rs` | 74 passed, no skips |
| `node --test tests/web_reveal.test.cjs` | 13 passed, no failures or skips; Node 24.21.0; controlled minimal DOM, not a full-browser test |
| `python -m pip check` | No broken requirements found |
| Installed package, outside source directory | CLI, Tk GUI, web resources and all 11 PNG assets present; module and console CLI help entry points worked |
| Installed Tk reveal | Real 15.5-second wait confirmed default 15-second masking; not a full five-minute idle test |
| Candidate Linux CI, Python 3.11 and 3.12 | Each job: 74 Python tests, 13 frontend tests, no skips, dependency check passed |
| Integrated main Linux CI, Python 3.11 and 3.12 | Each job: 74 Python tests, 13 frontend tests, no skips, dependency check passed |
| Source archive inventory and text-pattern review | README, submission handoff, launcher, all three Python test files and Node test file present; no tracked vaults, virtual environment, environment file or private-key artifacts found; observed password constants were explicit synthetic test fixtures |

The four requirements are mapped in the README: Argon2id master-passphrase
processing, a derived AES key, authenticated AES-GCM vault storage and password
generation with Python `secrets`. The README explains salts, nonces, AAD, KDF
costs, uniform sampling, authenticated rejection and limitations.

The suites cover creation, persistence, lock/reopen, wrong passwords, tampering,
duplicate labels, cancellation, write failure and reveal logic. Passing tests do
not prove the absence of every defect or replace the actual-machine demonstration.

The existing Windows rehearsal in `docs/SUBMISSION.md` is prior team evidence;
it was not independently repeated in this final macOS review. CI currently emits
an Actions Node-runtime deprecation warning; it did not cause either job to fail.

## Confirmed limitation: stale same-name entry replacement

An isolated synthetic-data check reproduced stale replacement deletion through
the desktop, CLI confirmation flow and web session. If client A sees entry X,
and client B deletes/recreates X, A can delete the replacement by name. File
locks serialize operations but do not compare record revisions. The web
`vault_epoch` changes on unlock, not on each entry mutation.

This predates PR #7 and does not prevent clean installation or a single-client
course demonstration. It is not limited to the web UI. Avoid concurrent changes
to the same vault. A future fix should reject stale expected record versions
under the existing file lock and include regression coverage. No fix is claimed
in this documentation-only update.

## Final handoff checklist

### Repository facts verified

- [x] PR #7 merged; integrated tree matches the reviewed application.
- [x] Matching main CI passed, including both Python versions and frontend tests.
- [x] Source archive includes desktop, CLI, assets, docs and tests.
- [x] Clean installation and package-resource checks completed.
- [x] Repository is public; default branch is main.
- [x] Existing synthetic-data and concurrent-use boundaries are documented.

### Still requires the team or instructor

- [ ] Obtain the complete Project 2 brief and reconcile every scoring item.
- [ ] Confirm submission destination, exact deadline/timezone and accepted format.
- [ ] Both teammates confirm their names/IDs and any contribution statement.
- [ ] Rehearse on the actual presentation machine with synthetic data, including
  restart, wrong password, reveal timeout and five-minute idle locking.
- [ ] Confirm course rules on AI assistance and third-party meme assets.
- [ ] Check the exact final commit and its own CI if submitting a later revision.
- [ ] Upload the requested deliverable and retain the instructor/portal receipt.

## Source packaging

Prefer a GitHub source archive for the chosen commit, or generate a tracked-files
archive from a clean checkout. Do not ZIP the entire working folder: it may
contain ignored vaults, credentials, virtual environments or build output.

```sh
git rev-parse HEAD
git archive --format=zip --output=../Hakimino-Project-2-source.zip HEAD
```

Record that SHA alongside the archive, extract it to a new directory, and follow
`docs/SUBMISSION.md`. Never include real credentials or personal vault files.
A public repository, approval or green CI is not evidence of instructor receipt.
