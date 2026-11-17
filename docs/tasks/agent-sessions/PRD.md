# PRD: Export Copilot Agent Sessions for a PR

## Objective

Add an `--export-agent-sessions` mode that exports every Copilot agent session recorded for a pull request. That covers Copilot code review passes and coding-agent runs. The export writes the curated session metadata, the raw session log, a readable transcript and, for code review sessions, the stored review findings with their file, line range, type and suggested fix. A reviewer or a review agent can then work from what Copilot already found instead of repeating it.

## Background

prinfo exports a PR's check logs, comments with review-thread state, and commit data through the GitHub CLI. The richest output of a Copilot code review, however, never reaches the PR. The posted review is a summary. The session log holds every finding the reviewer stored, the inline fix it generated or the reason it skipped one, and the pass number and head revision it reviewed.

That data is reachable only through the Copilot API host, not through the GitHub REST host that `gh api` targets:

- The documented agent tasks API (`agents/repos/{owner}/{repo}/tasks`) does not list Copilot code review tasks. A probe returned zero tasks for a repository with several reviewed PRs (`open_questions.md` Q2).
- `GET <copilot-api>/agents/sessions/resource/pull/{pr_database_id}` lists every session of a PR. `GET <copilot-api>/agents/sessions/{id}` returns session metadata, and `GET <copilot-api>/agents/sessions/{id}/logs` returns the log as server-sent events.
- `gh api` cannot call that host: it sends its own token scheme, and the host answers HTTP 400. A bearer token from `gh auth token` works (Q3).

## Requirements

### REQ-1: CLI option and env key

- `--export-agent-sessions` (`store_true`) and `PRINFO_EXPORT_AGENT_SESSIONS` enable the mode. The CLI flag overrides the env file, as for the other `--export-*` modes.
- `--skip-check-logs` accepts `--export-agent-sessions` as a valid companion mode. Its error message and help text list the new mode.
- `AppConfig` gains `export_agent_sessions: bool`.

### REQ-2: Session discovery

- The PR database id is read from `GET repos/{owner}/{repo}/pulls/{n}` (field `id`) through `gh`.
- Sessions are listed from `GET <copilot-api>/agents/sessions/resource/pull/{pr_database_id}`.
- Every listed session is exported, whatever its agent type, ordered by `created_at` ascending, ties broken by session id.
- A PR with no sessions produces an empty manifest (`sessions: []`) and a mode result, not an error.

### REQ-3: Copilot API client

- The host is derived from the GitHub host. `github.com` maps to `https://api.githubcopilot.com`, and `<tenant>.ghe.com` maps to `https://copilot-api.<tenant>.ghe.com`. Any other host skips the mode with reason code `unsupported_host` and makes no HTTP call.
- Requests use `urllib.request` with an `Authorization: Bearer <token>` header and a generic `User-Agent` (`prinfo/<version>`). No new runtime dependency is added.
- The token comes from `--gh-token` / `PRINFO_GH_TOKEN` when set. Otherwise it comes from `gh auth token --hostname <host>`, run with the same `GH_CONFIG_DIR` override as every other `gh` call.
- The token never appears in a log line, an exception message, a manifest or any written file. Tests assert this.
- The HTTP opener can be injected, so tests make no network calls.

### REQ-4: Session output files

Under `<output-dir>/agent-sessions/`:

- `agent-sessions.json` is the manifest. Keys: `repo`, `pr_number`, `copilot_api_host`, `mode_skip`, `sessions`, `skipped_sessions`, `counts`. `mode_skip` is `null`, or `{reason_code, reason}` when the whole mode was skipped (`unsupported_host`, `no_copilot_access`, `no_sessions_endpoint`); added by `solution_01.md` (drift D2).
- `<session_id>/session.json` holds curated metadata only: `id`, `name`, `agent_slug`, `event_type`, `state`, `created_at`, `completed_at`, `last_updated_at`, `model`, `head_ref`, `base_ref`, `workflow_run_id`, `error`. Values decoded from `event_identifiers` are added when present: `review_pass`, `head_sha`, `last_reviewed_head_revision`, `review_effort_level`.
- The identifying fields (user login, user tracking id, request ids, access type) and the internal settings blob are not written to `session.json` or to the manifest.
- `<session_id>/log.sse` holds the log bytes exactly as returned.
- Each manifest session entry lists the relative paths of the files written for it.

### REQ-5: Log parsing

- The parser reads `data:` lines of the SSE stream as JSON. A line that does not parse is counted in `unparsed_events`; the parser does not stop.
- `<session_id>/transcript.md` lists, in stream order, the assistant text and every tool call with its name and arguments. Arguments longer than 4000 characters are truncated, with a note saying they were truncated.
- `<session_id>/findings.json` is written only when the log holds at least one `store_comment` tool call. Each finding records `type`, `path`, `start_line`, `end_line`, `body`, `suggested_fix` (or `null`), `fix_skip_reason` and `fix_skip_note` (or `null`), in stream order.
- The parser keeps unknown argument keys under `extra` rather than dropping them.

### REQ-6: Failure handling

- HTTP 401 and 403 from session discovery skip the mode with reason code `no_copilot_access`. HTTP 404 skips it with `no_sessions_endpoint`. Neither is a crash, and the other modes of the run continue (the per-mode isolation in `src/prinfo/cli.py`).
- A metadata or log fetch that fails for one session records that session under `skipped_sessions` with a reason code, and the remaining sessions still export.
- When every listed session fails, the mode raises `ExportError`.
- The mode summary logs exported and skipped counts, with the same severity split as the other modes.

### REQ-7: Documentation

- `README.md` documents the option, the env key, the output files, the host mapping, the skip reason codes, and that the Copilot API endpoints are undocumented and may change.
- `skills/prinfo/SKILL.md` and its `references/commands.md`, `references/outputs.md` and `references/troubleshooting.md` cover the new mode.

### REQ-8: Version bump

- `pyproject.toml` goes from `0.4.0` to `0.5.0`, `uv.lock` is refreshed with `uv lock`, and `uv run prinfo --version` prints `prinfo 0.5.0`.

## Non-Requirements

- Requesting a Copilot review, waiting for a session to finish, following a live log, or any other write to the PR. prinfo stays a read-only exporter (Q1).
- Changes to PR-review skills outside this repository, such as inline pending reviews, suggestion blocks, thread replies and reviewer ensembles. They consume this export and are tracked separately (Q1).
- A Copilot API host override option, and GitHub Enterprise Server support (Q4).
- An option to write the full, unredacted session metadata (Q7).
- Review-thread resolution state. `--export-comments` already exports it (Q11).
- The documented agent tasks API (Q2).

## Acceptance Criteria

- **AC-1** - `--export-agent-sessions` and `PRINFO_EXPORT_AGENT_SESSIONS=true` both enable the mode, and `--skip-check-logs --export-agent-sessions` is accepted (REQ-1)
- **AC-2** - Against a faked Copilot API with two sessions for the PR, both are exported in `created_at` order, and a PR with no sessions yields `sessions: []` (REQ-2)
- **AC-3** - Host mapping is correct for `github.com`, a `<tenant>.ghe.com` host and an Enterprise Server host, and the last makes no HTTP call (REQ-3)
- **AC-4** - A test with a known token value finds that value in no captured log record, no exception text and no written file (REQ-3, REQ-4)
- **AC-5** - `session.json` and the manifest contain the curated keys and none of the identifying fields, and `log.sse` is byte-identical to the served log (REQ-4)
- **AC-6** - A recorded fixture log yields a transcript in stream order and a `findings.json` whose entries match the fixture's `store_comment` calls, including one with a suggested fix and one with a skip reason. A log without `store_comment` calls writes no `findings.json` (REQ-5)
- **AC-7** - HTTP 401, 403 and 404 on discovery produce the documented skip reason codes while another requested mode still exports. One failing session is skipped while the others export, and all sessions failing raises `ExportError` (REQ-6)
- **AC-8** - README and the bundled skill describe the option, env key, outputs, host mapping and skip reasons, and `markdownlint-cli2` passes (REQ-7)
- **AC-9** - `uv run prinfo --version` prints `prinfo 0.5.0` (REQ-8)
- **AC-10** - A manual run against a real PR with Copilot review sessions writes the manifest, both session folders and a non-empty `findings.json` (REQ-2, REQ-3, REQ-5)

## Deliverables

| Deliverable | Type |
| ----------- | ---- |
| `src/prinfo/copilot.py` | Create |
| `src/prinfo/session_log.py` | Create |
| `src/prinfo/gh.py` | Update |
| `src/prinfo/exporter.py` | Update |
| `src/prinfo/config.py` | Update |
| `src/prinfo/cli.py` | Update |
| `tests/test_copilot.py` | Create |
| `tests/test_session_log.py` | Create |
| `tests/fixtures/agent_session_log.sse` | Create |
| `tests/test_exporter.py` | Update |
| `tests/test_config.py` | Update |
| `tests/test_cli.py` | Update |
| `tests/test_gh.py` | Update |
| `README.md` | Update |
| `skills/prinfo/SKILL.md` | Update |
| `skills/prinfo/references/commands.md` | Update |
| `skills/prinfo/references/outputs.md` | Update |
| `skills/prinfo/references/troubleshooting.md` | Update |
| `pyproject.toml` | Update |
| `uv.lock` | Update |
