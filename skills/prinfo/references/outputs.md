# Output Interpretation

`prinfo` writes one directory per run. By default that directory is
`artifacts/pr-<pr-number>`.

## Files written

- `manifest.json`
- one `*.log` file for each exported GitHub Actions job

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

Each `skipped` entry includes:

- `check`
- `reason`

## How to explain skipped checks

Use the recorded `reason` instead of guessing. The current implementation
skips checks in two common cases:

- the check is not a GitHub Actions job
- GitHub exposes the check, but the job log endpoint returns `404` or
  `Not Found`

## When the command fails instead of writing output

Expect the command to fail when:

- no checks are found for the PR
- checks exist, but none expose downloadable job logs

In that case, explain the failure and suggest the next verification step, such
as checking whether the PR relies on external CI instead of GitHub Actions.
