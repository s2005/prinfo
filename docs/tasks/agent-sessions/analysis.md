# Analysis: Export Copilot Agent Sessions for a PR

## Goal

Export the Copilot agent sessions of a PR, above all the Copilot code review passes, into a local folder in the same style as the other prinfo modes. The parsed review findings are the part a consumer needs most (REQ-2 to REQ-5).

## Current Behavior

- Every remote call goes through `GhCli._run_command` (`src/prinfo/gh.py:408`), which runs `gh` with `GH_HOST`, `GH_TOKEN` and `GH_CONFIG_DIR` overrides set in `GhCli.__init__` (`src/prinfo/gh.py:152-168`). There is no HTTP client of its own.
- Export modes are independent functions in `src/prinfo/exporter.py`: `export_pr_check_logs` (line 102), `export_pr_comments` (line 214), `export_pr_commit_files` (line 323) and `export_pr_commit_log` (line 384). Each returns a result dataclass, and `main` runs each inside its own `try` block (`src/prinfo/cli.py:120-140`). The run fails only when no mode returned a result.
- `export_pr_comments` already shows the per-source skip pattern: a failing source becomes a `_skipped_source_record` (`src/prinfo/exporter.py:596`), and the mode raises `ExportError` only when every source failed. The new mode follows the same pattern per session.
- `resolve_config` (`src/prinfo/config.py:34-90`) resolves each `--export-*` flag against a `PRINFO_EXPORT_*` env key through `_resolve_bool`. It rejects `--skip-check-logs` unless another mode is enabled (`src/prinfo/config.py:56`).
- `--export-comments` already exports review-thread state (`isResolved`, `isOutdated`) through GraphQL (`src/prinfo/gh.py:22-27`), so the thread-state part of the originating proposal is already covered.
- `tests/test_exporter.py:30` fakes `GhCli` with `FakeGhCli`, and `tests/test_gh.py` injects a `runner` callable. No test performs network I/O.

## Feasibility

The endpoints were probed on a data-residency tenant (`open_questions.md` Q2, Q3):

| Call | Result |
| ---- | ------ |
| `gh api agents/repos/{owner}/{repo}/tasks` | 200, but zero tasks; code review tasks are not listed |
| `gh api agents/repos/{owner}/{repo}/tasks/{task_id}` | 200; returns the task and its sessions when the task id is already known |
| `gh api <copilot-api-url>` | 400, `Authorization header is badly formatted` |
| `GET <copilot-api>/agents/sessions/resource/pull/{pr_database_id}` with a bearer token | 200, `{"sessions": [...]}`, one entry per review pass |
| `GET <copilot-api>/agents/sessions/{id}` | 200, metadata including `agent_slug`, `event_type`, `resource_number`, `workflow_run_id` and a serialized `event_identifiers` blob |
| `GET <copilot-api>/agents/sessions/{id}/logs` | 200, server-sent events (`data: {...}` lines with `choices[].delta.content` and `choices[].delta.tool_calls[]`) |

The code review stores each finding as a `store_comment` tool call. Its arguments hold `comment_content`, `comment_type`, `file_location`, `start_line`, `end_line`, `fixed`, and either `suggested_fix` or `fix_skip_reason` and `fix_skip_note`. Parsing is a small, pure function.

The work is straightforward. The one structural change is an HTTP path next to the `gh` path.

## Approach

### Option A: `urllib` client with a token from `gh` (recommended)

A small `CopilotApiClient` in `src/prinfo/copilot.py` takes a base URL, a token provider and an injectable opener. `GhCli` gains `get_pull_request_id(repo, pr)` and `auth_token()`. `auth_token` returns the explicit token, or else the captured stdout of `gh auth token --hostname <host>`.

| Advantages | Disadvantages |
| ---------- | ------------- |
| No new dependency; the standard library covers the HTTP need | A second transport to test and maintain |
| Token stays in memory; never on a command line | `gh auth token` output must be handled as a secret in code paths and errors |
| Honours `--gh-token` and `--gh-config-dir` unchanged | |

### Option B: `gh api` with an explicit header

| Advantages | Disadvantages |
| ---------- | ------------- |
| Keeps one transport | Token on the `gh` command line, readable by other processes |
| | Depends on `gh` letting a `-H` header replace its own auth header, which is unverified |

### Option C: shell out to `curl`

| Advantages | Disadvantages |
| ---------- | ------------- |
| Header can be passed on stdin | External binary dependency for one mode; harder to fake in tests |

Option A is chosen (Q3).

## Implementation Notes

- **Host mapping (REQ-3).** `copilot_api_base_url(gh_host) -> str | None`. `github.com` maps to `https://api.githubcopilot.com`. A host matching `^[a-z0-9-]+\.ghe\.com$` maps to `https://copilot-api.<host>`. Anything else returns `None`, which the exporter turns into an `unsupported_host` skip.
- **Token hygiene (REQ-3).** `auth_token()` returns the token without logging it. `CopilotApiError` messages carry the method, the path and the HTTP status only: never headers, and the response body only when it holds no token (an `Authorization` substring check is enough). The `gh auth token` failure message reuses the stderr-based `GhCliError`, which prints no token.
- **PR id (REQ-2).** Reuse `_run_json` with `["api", f"repos/{owner}/{name}/pulls/{n}", "--hostname", host]` and read `id`.
- **Metadata curation (REQ-4).** `event_identifiers` is a list of strings shaped `<scheme>:<json>`. Split on the first `:`, parse the JSON, read only the four keys listed in REQ-4, and drop the rest. If parsing fails, those keys are omitted; it is not an error.
- **SSE parsing (REQ-5).** Iterate the decoded text line by line and keep lines starting with `data:`. Content deltas are separate events, and each is written as its own transcript block. The stream observed shows complete messages per event, so no delta merging is attempted. Tool calls read `function.name` and `function.arguments`; arguments are JSON-decoded for `store_comment` and written verbatim otherwise.
- **Decoding.** The log is decoded as UTF-8 with `errors="replace"` for parsing only, while `log.sse` keeps the original bytes. Output files are written with `encoding="utf-8"`, so Windows code pages cannot raise `UnicodeEncodeError`.
- **Paths.** The session id is used as a folder name only after a `^[A-Za-z0-9-]+$` check, and an id that fails it is skipped with `invalid_session_id`. This is the same caution as `_sanitize_repo_relative_path` (`src/prinfo/exporter.py:544`).
- **Ordering (REQ-2).** Sort by `(created_at or "", id)`.

## Risks

| Risk | Mitigation |
| ---- | ---------- |
| The Copilot API endpoints are undocumented and may change or disappear | Raw log kept as `log.sse`; failures are skips with reason codes; README states the status |
| SSE event shape changes, so the parser misses findings | Unparsed lines counted in the manifest; unknown `store_comment` keys kept under `extra`; raw log available |
| Token leaks through an exception or debug log | Single construction point for the header; a test scans logs, errors and output files for a sentinel token (AC-4) |
| `github.com` host mapping untested against a live account | Mapping taken from GitHub's own CLI and docs; unit-tested; manual check on a `github.com` PR listed as optional in verification |
| Large logs (hundreds of KB per pass) | Streamed to disk once; parsing is linear |
| Session metadata carries identifying data | Curated subset only in `session.json` and the manifest (Q7) |

## Test Strategy

- **Unit, `tests/test_copilot.py`:** host mapping; header construction; error mapping for 401, 403, 404 and 500; the token absent from error text; a fake opener records requests, so there is no network I/O.
- **Unit, `tests/test_session_log.py`:** parse the recorded fixture into a transcript and findings; check unparsed-line counting, truncation, a log with no findings, and keys preserved under `extra`.
- **Unit, `tests/test_gh.py`:** `get_pull_request_id` and `auth_token` with an injected runner, and the explicit token winning over `gh auth token`.
- **Unit, `tests/test_exporter.py`:** the full mode against `FakeGhCli` and a fake Copilot client. Cover ordering, an empty PR, per-session skip, all sessions failing, the unsupported host, curated metadata and the sentinel-token scan.
- **Unit, `tests/test_config.py` and `tests/test_cli.py`:** flag and env resolution, the `--skip-check-logs` companion, and isolation of the new mode's failure from another mode.
- **Fixture:** `tests/fixtures/agent_session_log.sse` is a synthetic log modelled on the observed shape. It holds no real repository, user or tenant data.
- **Manual:** one run against a real PR with Copilot review sessions (AC-10). Its output stays outside the repository.
