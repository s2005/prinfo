# Troubleshooting

Use this file when the user asks why `prinfo` failed or produced incomplete
output.

## `gh` is missing

Symptom:

- error says GitHub CLI `gh` is not installed or not available on `PATH`

Action:

- install `gh`
- verify `gh auth status`
- rerun `uv run prinfo ...`

## PR number is missing or invalid

Symptom:

- configuration error says the PR number must be provided
- configuration error says the PR number must be an integer

Action:

- pass `--pr <number>`
- or provide `PRINFO_PR` in the env file

## Env file path is wrong

Symptom:

- configuration error says the env file does not exist

Action:

- fix `--env-file`
- or remove it and rely on `.env` in the current directory

## Repository cannot be resolved

Symptom:

- `prinfo` fails when `--repo` is omitted outside a repository checkout
- `gh repo view` cannot determine `nameWithOwner`

Action:

- rerun with `--repo owner/repo`
- for GitHub Enterprise use `--repo host/owner/repo` and `--gh-host host`

## No checks found

Symptom:

- command fails with a message that no checks were found for the PR

Action:

- verify the PR number
- verify the repository
- confirm that the PR has status checks in GitHub

## Checks were found but logs were skipped

Symptom:

- `manifest.json` contains skipped checks
- logs are missing for some checks

Action:

- inspect the recorded `reason` in the manifest
- expect non-GitHub Actions checks to be skipped
- expect missing downloadable logs when GitHub returns `404`

## No logs exported at all

Symptom:

- command fails even though the PR has checks

Action:

- verify whether every check is external CI instead of GitHub Actions
- verify whether all Actions checks lack a downloadable job log
- inspect the PR checks in GitHub before retrying
