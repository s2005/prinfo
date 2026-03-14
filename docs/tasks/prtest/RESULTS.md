# Self-Test Results

## PR Under Test

- Repository: `s2005/prinfo`
- PR: [#1](https://github.com/s2005/prinfo/pull/1)
- Title: `Add CI workflow for PR self-test`
- Base branch: `main`
- Head branch: `codex/pr-ci-self-test`

## GitHub Actions Result

All seven GitHub Actions checks for the PR completed successfully:

- `Lint`
- `Test (ubuntu-latest, Python 3.11)`
- `Test (ubuntu-latest, Python 3.13)`
- `Test (windows-latest, Python 3.11)`
- `Test (windows-latest, Python 3.13)`
- `Test (macos-latest, Python 3.11)`
- `Test (macos-latest, Python 3.13)`

## prinfo Run

Command used:

```bash
uv run prinfo --repo s2005/prinfo --pr 1 --output-dir artifacts/prtest-pr-1
```

Observed result:

- Exported logs: `7`
- Skipped checks: `0`
- Manifest: `artifacts/prtest-pr-1/manifest.json`

Exported log files:

- `01-ci-lint-job-67061562310.log`
- `02-ci-test-ubuntu-latest-python-3.11-job-67061562318.log`
- `03-ci-test-ubuntu-latest-python-3.13-job-67061562321.log`
- `04-ci-test-windows-latest-python-3.11-job-67061562324.log`
- `05-ci-test-windows-latest-python-3.13-job-67061562337.log`
- `06-ci-test-macos-latest-python-3.11-job-67061562320.log`
- `07-ci-test-macos-latest-python-3.13-job-67061562317.log`

The self-test confirmed that `prinfo` can export logs from its own GitHub
Actions pull request checks on this repository.
