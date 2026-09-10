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
- inspect `reason_code` to distinguish unsupported checks from missing
  downloadable log content
- expect non-GitHub Actions checks to be skipped
- expect missing downloadable logs when GitHub returns `404`

## A check exported but the log is empty

Symptom:

- an `exported` manifest entry has `has_log_content` set to `false`
- the file is zero bytes, or `path` is empty when `--skip-empty-logs` was used

Action:

- inspect `empty_log_reason` in the manifest
- if `conclusion` is `SKIPPED`, treat an empty log as expected behavior
- if `saved` is `false`, confirm whether the run used `--skip-empty-logs`
- if `saved` is `true` and the file is zero bytes, explain that the job
  exposed a log endpoint but returned no content

## No logs exported at all

Symptom:

- command fails even though the PR has checks

Action:

- verify whether every check is external CI instead of GitHub Actions
- verify whether all Actions checks lack a downloadable job log
- inspect the PR checks in GitHub before retrying

## `--skip-check-logs` was rejected

Symptom:

- a configuration error names `--export-commit-files`, `--export-comments`
  and `--export-commit-log` and their three env keys

Action:

- `--skip-check-logs` only suppresses the check-log export, it is not an
  export mode on its own
- add at least one of the three export flags, or set the matching env key

## A comment source was skipped

Symptom:

- `comments.json` has one or more entries under `skipped_sources`
- the matching entry in `counts` is `0`

Action:

- read the recorded `source`, `reason_code` and `reason` instead of guessing
- each of the four sources is fetched independently, so the remaining
  sources still exported
- a `404` usually means the endpoint is unavailable for that PR or the token
  cannot read it

## Review comments have no resolved state

Symptom:

- every entry in `review_comments` has `is_resolved` and `thread_id` set to
  `null`

Action:

- check whether `skipped_sources` holds a `review_threads` entry - if it
  does, the GraphQL call failed and resolved state is simply unavailable for
  that run while the three REST sources still exported
- verify the token can read the repository and that the host supports the
  `reviewThreads` field

## One review comment has no resolved state while others do

Symptom:

- `review_threads` is populated and most comments carry `is_resolved`, but a
  few are `null`

Action:

- this is expected, not a failure
- the comment is not part of a review thread, or its thread reported more
  than 100 comments and the tail was not returned
- treat `null` as "no thread matched" rather than "unresolved"

## No comment data was exported

Symptom:

- the command fails saying no comment data could be exported for the PR

Action:

- every one of the four sources failed, which usually points at
  authentication or repository access rather than the PR
- verify `gh auth status`, the repository reference and `--gh-host` for
  GitHub Enterprise

## The commit log export failed

Symptom:

- the command fails saying no commits were found for the PR

Action:

- verify the PR number and repository, and confirm the PR actually has
  commits
- `--export-commit-log` downloads no file content, so a failure here is
  about the commit listing and not about file downloads

## Some export modes succeeded and others failed

Symptom:

- the command exits `0` but a warning names a mode that failed

Action:

- each requested mode runs independently, so the run exits non-zero only
  when no mode produced a result
- read the per-mode warning to see which one failed and treat the exported
  outputs of the other modes as valid
