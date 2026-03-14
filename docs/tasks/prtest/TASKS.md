# Tasks

## Planned

- Create a feature branch for CI and self-test work.
- Add a GitHub Actions workflow that runs linting and tests on pull requests.
- Document the PR self-test flow in this task folder.
- Open a PR against `main` so GitHub Actions produces real checks.
- Run `prinfo` against that PR and capture the output here.

## Completed

- Created branch `codex/pr-ci-self-test`.
- Added GitHub Actions CI for pull requests and pushes to `main`.
- Added local documentation for the CI and self-test flow.
- Verified locally with `pytest`, `ruff`, `markdownlint-cli2`, and
  `prinfo --help`.
- Opened PR [#1](https://github.com/s2005/prinfo/pull/1) against `main`.
- Verified that all seven GitHub Actions checks passed on the PR.
- Ran `prinfo` against `s2005/prinfo#1` and exported all seven job logs.
