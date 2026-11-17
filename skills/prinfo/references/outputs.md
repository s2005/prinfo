# Output Interpretation

`prinfo` writes one directory per run. By default that directory is
`artifacts/pr-<pr-number>`.

## Files written

- `manifest.json`
- one `*.log` file for each exported GitHub Actions job
- `comments.json`, produced by `--export-comments`
- `comments.md`, produced by `--export-comments`
- `commit-log.json`, produced by `--export-commit-log`
- `agent-sessions/`, produced by `--export-agent-sessions`

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

Use `reason_code` to distinguish those cases structurally, and to tell a skip
that needs action from one that does not:

- `unsupported_check_type` - the check is not a GitHub Actions job, so it never
  had a log to download. Normal, not actionable. Logged per check at INFO.
- `missing_log_content` - a real Actions job did not return the log it should
  have. This is the one worth investigating; inspect `reason` for the
  underlying `gh` error. Logged per check at WARNING.

The command summary applies the same split. It warns about the
`missing_log_content` count and reports the `unsupported_check_type` count at
INFO, so a run whose every skipped check is `unsupported_check_type` produces
no warning at all. Do not read a missing warning as "no checks were skipped" -
read the INFO line, or the `skipped` array in `manifest.json`.

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

## Commit files manifest structure

`commits-manifest.json`, produced by `--export-commit-files`, has six
top-level keys:

- `repo`
- `pr_number`
- `commit_count`
- `exported_files`
- `skipped_files`
- `commits`

Each entry in `commits` carries:

- `commit`
- `folder`
- `manifest_path`
- `exported_files`
- `skipped_files`
- `skipped`

The per-commit `skipped` array mirrors the `skipped` list written to that
commit's own `_commit.json`. Each entry carries `path`, `status`,
`additions`, `deletions`, `changes`, `previous_path`, `reason_code`, and
`reason`, so the reason for every skipped file is readable from
`commits-manifest.json` alone, without opening each commit folder.

## How to explain a skipped commit file

Use the recorded `reason_code` in a commit's `skipped` entries instead of
treating every skip the same way:

- `removed` - the file was deleted in that commit, so it cannot be
  downloaded at that revision. Normal, not actionable.
- `missing_path` - the commit payload did not include a path for the file.
  Normal, not actionable.
- `download_failed` - `gh` errored while downloading the file. This is the
  one worth investigating; inspect `reason` for the underlying `gh` error.

## How to explain a skipped comment source

Use the recorded `source`, `reason_code`, and `reason` in `skipped_sources`
instead of guessing. A `review_threads` entry means resolved state is simply
unavailable for that run, while the REST comments (issue comments, review
comments, and reviews) still exported.

## Agent sessions structure

`--export-agent-sessions` writes an `agent-sessions/` folder:

```text
agent-sessions/
  agent-sessions.json
  <session_id>/
    session.json
    log.sse
    transcript.md
    findings.json
```

`findings.json` exists only when the log holds `store_comment` calls. The
Copilot API endpoints are undocumented and may change, so the raw `log.sse`
is kept unchanged next to the parsed files.

`agent-sessions.json` has seven top-level keys:

- `repo`
- `pr_number`
- `copilot_api_host`
- `mode_skip`
- `sessions`
- `skipped_sessions`
- `counts`

`copilot_api_host` is `api.githubcopilot.com` for `github.com`,
`copilot-api.<tenant>.ghe.com` for `<tenant>.ghe.com`, and `null` for any
other host. `mode_skip` is `null` or an object with `reason_code` and
`reason`. `counts` holds `listed`, `exported`, `skipped`, and `findings`.

Each `sessions` entry carries the curated session fields plus `files`
(`session`, `log`, `transcript`, `findings`; `findings` is `null` when no
findings file was written), `findings_count`, `unparsed_events`, and
`log_bytes`. Each `skipped_sessions` entry carries `session_id`,
`reason_code`, and `reason`.

`session.json` keeps only `id`, `name`, `agent_slug`, `event_type`, `state`,
`created_at`, `completed_at`, `last_updated_at`, `model`, `head_ref`,
`base_ref`, `workflow_run_id`, and `error`, plus `review_pass`, `head_sha`,
`last_reviewed_head_revision`, and `review_effort_level` when present.
Identifying fields (user login, user ids, request ids, access type,
settings) are dropped.

Each finding carries `type`, `path`, `start_line`, `end_line`, `body`,
`suggested_fix`, `fix_skip_reason`, `fix_skip_note`, `fixed`, and `extra`
(any other `store_comment` argument, kept rather than dropped).

`transcript.md` has numbered headings for assistant text and tool calls.
Tool-call arguments over 4000 characters are truncated and a note gives the
shown and total character counts. `unparsed_events` counts log events that
could not be parsed.

## How to explain a skipped agent session

A `mode_skip` stops the whole mode and is logged at `WARNING`:

- `unsupported_host` - the repository host has no Copilot API host; no HTTP
  call was made
- `no_copilot_access` - the sessions request returned HTTP 401 or 403
- `no_sessions_endpoint` - the sessions request returned HTTP 404

A `skipped_sessions` entry affects one session:

- `metadata_unavailable` and `log_unavailable` - the Copilot API failed to
  serve a listed session. Worth investigating; logged at `WARNING`.
- `invalid_session_id` - the id cannot be used as a folder name. Normal, not
  actionable; logged at `INFO`.

## When the command fails instead of writing output

Expect the command to fail when:

- no checks are found for the PR
- checks exist, but none expose downloadable job logs
- every comment source failed during `--export-comments`
- the PR has no commits during `--export-commit-log`
- sessions were listed but none could be exported during
  `--export-agent-sessions`, or listing sessions failed with an error other
  than a mode skip

In that case, explain the failure and suggest the next verification step, such
as checking whether the PR relies on external CI instead of GitHub Actions.
