# Output Interpretation

`prinfo` writes one directory per run. By default that directory is
`artifacts/pr-<pr-number>`.

## Files written

- `manifest.json`
- one `*.log` file for each exported GitHub Actions job

When `--skip-empty-logs` is used, empty logs are still recorded in
`manifest.json` but no zero-byte `.log` file is written for them.

## Log file naming

The current file naming format is:

```text
<index>-<workflow>-<check>-job-<job_id>.log
```

Example:

```text
03-ci-unit-tests-py311-job-2.log
```

The workflow and check name are slugified to lowercase and non filename-safe
characters are replaced with `-`.

## Manifest structure

The manifest currently contains:

- `repo`
- `pr_number`
- `exported`
- `skipped`

Each `exported` entry includes:

- `check`
- `path`
- `bytes`
- `saved`
- `status`
- `conclusion`
- `has_log_content`
- `empty_log_reason`

Each `skipped` entry includes:

- `check`
- `status`
- `conclusion`
- `has_log_content`
- `reason_code`
- `reason`

## How to explain skipped checks

Use the recorded `reason` instead of guessing. The current implementation
skips checks in two common cases:

- the check is not a GitHub Actions job
- GitHub exposes the check, but the job log endpoint returns `404` or
  `Not Found`

Use `reason_code` to distinguish those cases structurally:

- `unsupported_check_type`
- `missing_log_content`

## How to explain empty exported entries

If an `exported` entry has `has_log_content: false`, check:

- `empty_log_reason` to explain why it is empty
- `saved` to determine whether a zero-byte file was written
- `path` to see whether a file exists on disk for that entry

## When the command fails instead of writing output

Expect the command to fail when:

- no checks are found for the PR
- checks exist, but none expose downloadable job logs

In that case, explain the failure and suggest the next verification step, such
as checking whether the PR relies on external CI instead of GitHub Actions.
