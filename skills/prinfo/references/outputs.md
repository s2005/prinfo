# Output Interpretation

`prinfo` writes one directory per run. By default that directory is
`artifacts/pr-<pr-number>`.

## Files written

- `manifest.json`
- one `*.log` file for each exported GitHub Actions job
- `comments.json`, produced by `--export-comments`
- `comments.md`, produced by `--export-comments`
- `commit-log.json`, produced by `--export-commit-log`

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

## Comment manifest structure

`comments.json` has eight top-level keys:

- `repo`
- `pr_number`
- `issue_comments`
- `review_comments`
- `reviews`
- `review_threads`
- `counts`
- `skipped_sources`

An issue comment carries `author` and `author_type`, along with the fields
returned by the `issues/<n>/comments` endpoint.

A review comment carries `author`, `author_type`, `path`, `line`, `side`,
`in_reply_to_id`, `diff_hunk`, `is_resolved`, and `thread_id`.

A review carries `author`, `author_type`, and `state`, along with the other
fields returned by the `pulls/<n>/reviews` endpoint.

A review thread carries `thread_id`, `is_resolved`, `is_outdated`, and
`comment_ids`.

`counts` holds the per-source record count under the keys `issue_comments`,
`review_comments`, `reviews`, and `review_threads`.

A `skipped_sources` entry carries `source`, `reason_code`, and `reason`.

## Comment transcript structure

`comments.md` is ordered by timestamp across all sources, with untimestamped
entries last. Each section heading names the author, the source kind, and the
timestamp. A review heading also carries its state, and an inline review
comment heading carries `path:line` and its resolved state when a review
thread matched it. Bodies are reproduced verbatim.

## Commit log structure

`commit-log.json` has four top-level keys:

- `repo`
- `pr_number`
- `commit_count`
- `commits`

Each entry in `commits` carries thirteen fields: `sha`, `short_sha`,
`message_headline`, `message`, `author_name`, `author_email`,
`author_login`, `authored_date`, `committer_name`, `committer_email`,
`committer_login`, `committed_date`, and `url`.

Each commit record carries both the git author and the git committer, which
differ after a rebase or a squash merge. `author_login` and `committer_login`
are the corresponding GitHub accounts, resolved from the commit email, and
are `null` when that email matches no GitHub user.

## How to explain a skipped comment source

Use the recorded `source`, `reason_code`, and `reason` in `skipped_sources`
instead of guessing. A `review_threads` entry means resolved state is simply
unavailable for that run, while the REST comments (issue comments, review
comments, and reviews) still exported.

## When the command fails instead of writing output

Expect the command to fail when:

- no checks are found for the PR
- checks exist, but none expose downloadable job logs
- every comment source failed during `--export-comments`
- the PR has no commits during `--export-commit-log`

In that case, explain the failure and suggest the next verification step, such
as checking whether the PR relies on external CI instead of GitHub Actions.
