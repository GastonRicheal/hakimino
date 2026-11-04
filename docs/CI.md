# Continuous integration

The Tests workflow runs on pull requests targeting main and pushes to main.
Manual dispatch becomes available once the workflow is present on the default
branch. It uses Ubuntu 24.04 with Python 3.11 (the minimum supported version)
and Python 3.12. Both jobs execute the complete existing suite, including real
Tk widgets under Xvfb, with synthetic credentials in temporary directories.

## Checks

1. Install the package with its test dependencies and run `pip check`.
2. Print interpreter and dependency versions for reproducibility.
3. Create a real Tk root under the virtual display; a missing Tk runtime or
   inaccessible display is a failure, not an accepted skip.
4. Execute pytest with verbose output and a JUnit report.
5. Reject skipped tests, empty reports, failures/errors, or missing required GUI
   workflows. Keep the named GUI checks synchronized if those tests are renamed.
6. Check both module and installed CLI help entry points.

The workflow uses a read-only repository token, does not persist checkout
credentials, and requires no project secrets. Official checkout/setup-python
Actions are pinned to commit SHAs. Dependency versions are printed rather than
claimed to be locked. The 15-minute job limit bounds stalled tests. New runs
cancel older runs for the same PR/ref without cancelling other PRs.

## Reviewing results

Open the pull request's Checks tab and inspect both Python jobs. A workflow file
alone does not prove a successful run. Consult the actual run and logs before
claiming CI passed. This workflow does not change branch protection or merge PRs;
a repository administrator may separately configure these checks as required.

The existing baseline has 46 cases: 38 vault/CLI cases, one session case, and
seven Tk widget cases. GUI dialogs use supplied synthetic inputs and timers are
shortened in tests. Automated checks do not replace manual usability, full-length
idle timing, or verification on both teammates' machines. Tests also do not
certify production security or establish compliance with an unavailable full rubric.

## Local equivalent

Use Python >=3.11 with Tk installed and a working display:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pip check
.venv/bin/python -m pytest -v -ra
.venv/bin/python -m hakimino --help
.venv/bin/hakimino --help
```

On headless Linux prefix the pytest command with `xvfb-run -a`. On Windows use
`.venv\Scripts\python.exe` and `.venv\Scripts\hakimino.exe`. A machine without
Tk/display support is not a verified GUI environment.
