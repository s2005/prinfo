# prinfo

`prinfo` is a cross-platform Python CLI that uses GitHub CLI (`gh`) to
export pull request check logs into a local folder. It can also export the
files touched by each PR commit into per-commit folders, export the PR review
discussion, export the commit log, and export Copilot agent sessions. The current implementation focuses on
GitHub-backed PR metadata and writes manifests for all export modes.

This repository also includes an Agent Skill for running, troubleshooting,
and interpreting `prinfo`. Installation instructions are in
[INSTALL_SKILL.md](./INSTALL_SKILL.md).

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- GitHub CLI (`gh`) installed and authenticated for the target repository

## Install globally

To make `prinfo` available as a shell command outside this repository, install it as a
global `uv` tool from the checkout:

```bash
uv tool install --editable .
```

That exposes the `prinfo` command from uv's global tool bin directory while keeping it
linked to the local repository for editable development.

To install without cloning the repository first, install directly from Git:

```bash
uv tool install git+https://github.com/s2005/prinfo.git
```

That installs `prinfo` from the latest commit on the repository's default branch.

## Quick start

```bash
uv sync --dev
uv run prinfo --repo owner/repo --pr 123 --output-dir artifacts/pr-123
```

If you want empty job logs to appear only in `manifest.json` and not as zero-byte files:

```bash
uv run prinfo --repo owner/repo --pr 123 --skip-empty-logs
```

To export commit folders alongside the check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files
```

To export only commit folders and skip PR check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files --skip-check-logs
```

To export only the PR review discussion and skip PR check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-comments --skip-check-logs
```

To export only the commit log and skip PR check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-log --skip-check-logs
```

To export only the Copilot agent sessions (code review passes and coding-agent
runs) and skip PR check logs:

```bash
prinfo --repo OWNER/REPO --pr 123 --export-agent-sessions --skip-check-logs
```

You can also load configuration from an env file:

```bash
uv run prinfo --env-file some.env
```

Supported env-file keys:

- `PRINFO_PR`
- `PRINFO_REPO`
- `PRINFO_OUTPUT_DIR`
- `PRINFO_EXPORT_COMMIT_FILES`
- `PRINFO_EXPORT_COMMENTS`
- `PRINFO_EXPORT_COMMIT_LOG`
- `PRINFO_EXPORT_AGENT_SESSIONS`
- `PRINFO_SKIP_CHECK_LOGS`
- `PRINFO_GH_HOST`
- `PRINFO_GH_TOKEN`
- `PRINFO_GH_CONFIG_DIR`
- `PRINFO_LOG_LEVEL`

These keys are read from the env file only. They are not picked up from
exported shell variables.

CLI arguments override env-file values.

### Choosing the env file with PRINFO_ENV_FILE

`PRINFO_ENV_FILE` is read from the process environment, not from the env
file, so it cannot be set inside the file it names. It names the env file
that the keys listed above are read from.

`PRINFO_ENV_FILE` is the env counterpart of `--env-file`. When both are
given, `--env-file` takes precedence. When neither is given, `prinfo` falls
back to a `.env` file in the current directory if one exists.

## Multiple GitHub accounts

`prinfo` does not mutate your global `gh` login state. Instead, it
supports account selection by passing either:

- `PRINFO_GH_TOKEN` / `--gh-token`
- `PRINFO_GH_CONFIG_DIR` / `--gh-config-dir`

That lets you point `prinfo` at a different authenticated `gh` context per run.

## Output

The command writes:

- one `*.log` file for each exported GitHub Actions job
- `manifest.json` with exported and skipped checks
- optional `commits/<commit-sha>/...` folders when `--export-commit-files` is enabled
- optional `commits/<commit-sha>/_commit.json` per commit
- optional `commits-manifest.json` with the PR commit list, per-commit
  summaries, and why each skipped file was skipped
- optional `comments.json` and `comments.md` when `--export-comments` is enabled
- optional `commit-log.json` when `--export-commit-log` is enabled
- optional `agent-sessions/` folder when `--export-agent-sessions` is enabled

Checks that are not backed by GitHub Actions jobs are skipped and
recorded in the manifest under the reason code `unsupported_check_type`. That
skip is normal and nobody can act on it, so it is logged at `INFO` per check
and counted in an `INFO` summary line. A check that is a real Actions job but
returns no downloadable log is recorded as `missing_log_content` and logged at
`WARNING`, both per check and in the summary, because it is the one worth
investigating. A run whose every skipped check is `unsupported_check_type`
therefore produces no warning.

When `--skip-empty-logs` is enabled, empty logs are still recorded in the
manifest but their `path` is left empty and no zero-byte file is written.

When `--export-commit-files` is enabled, commit export still runs even if the
PR has no downloadable Actions logs. Removed files are recorded in commit
metadata as skipped because they cannot be downloaded at the target commit SHA.

`--skip-check-logs` requires at least one of the four export modes
(`--export-commit-files`, `--export-comments`, `--export-commit-log`,
`--export-agent-sessions`) and skips only the check-log export.

Each requested export mode runs independently, so one mode failing does not
stop the others, and the command fails only when no mode produced a result.

`comments.json` holds the PR review discussion: top-level keys `repo`,
`pr_number`, `issue_comments`, `review_comments`, `reviews`,
`review_threads`, `counts`, and `skipped_sources`. Records are exported
verbatim, with no bot filtering and no dropping of empty review bodies, and
every comment and review entry carries `author` and `author_type`. A comment
source that fails to fetch is recorded under `skipped_sources` while the
remaining sources still export.

`comments.md` is a readable transcript rendered from the same records,
ordered by timestamp across all sources with untimestamped entries last.

`commit-log.json` carries commit metadata only (`sha`, `short_sha`,
`message_headline`, `message`, `author_name`, `author_email`, `author_login`,
`authored_date`, `committer_name`, `committer_email`, `committer_login`,
`committed_date`, `url`) for every commit on the PR, with no file downloads.
Each commit record carries both the git author and the git committer, which
differ after a rebase or a squash merge; `author_login` and `committer_login`
are the corresponding GitHub accounts and are `null` when the commit email
matches no GitHub user.

### Agent sessions

`--export-agent-sessions` exports the Copilot agent sessions linked to the PR:
code review passes and coding-agent runs. It writes an `agent-sessions/`
folder inside the output directory:

```text
agent-sessions/
  agent-sessions.json
  <session_id>/
    session.json
    log.sse
    transcript.md
    findings.json
```

`findings.json` is written only when the session log holds `store_comment`
calls.

> The Copilot API endpoints behind this mode are undocumented and may change
> without notice. `log.sse`, the raw event-stream log, is kept unchanged for
> that reason, so nothing is lost when the parser misses a changed event
> shape.

`agent-sessions.json` is the manifest. Its keys are `repo`, `pr_number`,
`copilot_api_host`, `mode_skip`, `sessions`, `skipped_sessions`, and
`counts` (`listed`, `exported`, `skipped`, `findings`). Each `sessions` entry
holds the curated session fields plus `files` (the relative paths of
`session.json`, `log.sse`, `transcript.md`, and `findings.json`, the last
`null` when no findings file was written), `findings_count`,
`unparsed_events` (log events that could not be parsed and were left out of
the transcript), and `log_bytes`. Each `skipped_sessions` entry holds
`session_id`, `reason_code`, and `reason`.

`session.json` is curated rather than a copy of the API response. It keeps
only `id`, `name`, `agent_slug`, `event_type`, `state`, `created_at`,
`completed_at`, `last_updated_at`, `model`, `head_ref`, `base_ref`,
`workflow_run_id`, and `error`, plus `review_pass`, `head_sha`,
`last_reviewed_head_revision`, and `review_effort_level` when the session
carries them. Identifying fields (user login, user ids, request ids, access
type, and settings) are dropped.

Each finding in `findings.json` is one `store_comment` call and carries
`type`, `path`, `start_line`, `end_line`, `body`, `suggested_fix`,
`fix_skip_reason`, `fix_skip_note`, `fixed`, and `extra` (any other
`store_comment` argument, kept rather than dropped).

`transcript.md` lists the assistant text and the tool calls of the session in
order, with numbered headings. Tool-call arguments longer than 4000
characters are truncated, and the transcript says how many characters were
shown.

The Copilot API host is derived from the repository host, which defaults to
`--gh-host`:

| Repository host | Copilot API host |
| --------------- | ---------------- |
| `github.com` | `api.githubcopilot.com` |
| `<tenant>.ghe.com` | `copilot-api.<tenant>.ghe.com` |
| anything else | none; the mode is skipped as `unsupported_host` and no HTTP call is made |

The token comes from `--gh-token` / `PRINFO_GH_TOKEN` when set. Otherwise
`prinfo` runs `gh auth token --hostname <host>`, honouring `--gh-config-dir`.
The token is never written to disk or logged.

Skip reasons come at two levels. A mode skip stops the whole mode, is
recorded under `mode_skip` in the manifest, and is logged at `WARNING`:

- `unsupported_host` - the repository host has no known Copilot API host
- `no_copilot_access` - the sessions request returned HTTP 401 or 403
- `no_sessions_endpoint` - the sessions request returned HTTP 404

A per-session skip is recorded in `skipped_sessions` while the other sessions
still export:

- `metadata_unavailable` - the session metadata could not be fetched; logged
  at `WARNING`
- `log_unavailable` - the session log could not be fetched; logged at
  `WARNING`
- `invalid_session_id` - the session id cannot be used as a folder name;
  normal, logged at `INFO`

Any other failure while listing sessions fails the mode, and the other
requested modes continue. The mode also fails when sessions were listed but
every one of them failed to export.

## Skill

The `prinfo` skill lives in `skills/prinfo` and is intended for agent
workflows around:

- building the right `prinfo` command
- choosing `gh` authentication context
- interpreting `manifest.json`
- troubleshooting skipped checks and missing logs

See [INSTALL_SKILL.md](./INSTALL_SKILL.md) for installation steps for
Claude Code, VS Code, Cursor, and Codex.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

Markdown linting uses the repo-local
[.markdownlint-cli2.jsonc](./.markdownlint-cli2.jsonc) configuration and a
globally installed `markdownlint-cli2` binary:

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

## CI

GitHub Actions runs the following checks on pull requests:

- `ruff`
- `pytest`
- `markdownlint-cli2`
- CLI help smoke test on Windows, Linux, and macOS
