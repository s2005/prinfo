# Progress: Export Copilot Agent Sessions for a PR

## Status Legend

| Marker | Meaning |
| ------ | ------- |
| `[ ]` | Not started |
| `[x]` | Complete |
| `[~]` | In progress |
| `[!]` | Blocked or needs decision |
| `[-]` | Skipped / not applicable |

## Planning Checklist

- [x] Analyze current behavior.
- [x] Create open_questions.md and resolve every entry
- [x] Create analysis.md
- [x] Create PRD.md
- [x] Create implementation_plan.md
- [x] Create verification.md
- [x] Create progress.md

## Phase 1: Option, env key and version bump

Requirements: REQ-1, REQ-8

- [x] Add `export_agent_sessions` to `AppConfig` and `resolve_config` with `PRINFO_EXPORT_AGENT_SESSIONS`
- [x] Accept the mode as a `--skip-check-logs` companion and update the error message
- [x] Add `--export-agent-sessions` to the parser and update `--skip-check-logs` help
- [x] Bump `pyproject.toml` to `0.5.0` and run `uv lock` (also `src/prinfo/__init__.py`, see `notes.md` D1 and `solution_01.md`)
- [x] Config and CLI tests
- [x] Phase 1 verification

## Phase 2: Copilot API client and gh helpers

Requirements: REQ-3

- [x] `copilot_api_base_url` host mapping
- [x] `CopilotApiError` with token-free messages
- [x] `CopilotApiClient` with injectable opener and lazy token provider
- [x] `GhCli.get_pull_request_id`
- [x] `GhCli.auth_token` (optional `host` keyword, see `notes.md` D3)
- [x] `tests/test_copilot.py` and `tests/test_gh.py` additions
- [x] Phase 2 verification

## Phase 3: Session log parser

Requirements: REQ-5, REQ-4

- [ ] `parse_session_log` with unparsed-event counting
- [ ] `render_transcript` with argument truncation
- [ ] Findings extraction from `store_comment` calls with `extra`
- [ ] `curate_session_metadata` allow-list and `event_identifiers` decoding
- [ ] Synthetic fixture `tests/fixtures/agent_session_log.sse`
- [ ] `tests/test_session_log.py`
- [ ] Phase 3 verification

## Phase 4: Export mode

Requirements: REQ-2, REQ-4, REQ-6, REQ-3

- [ ] `AgentSessionExportResult`
- [ ] `export_pr_agent_sessions` with host, access and per-session skips
- [ ] Register the mode in `main` and extend `_log_mode_summaries`
- [ ] Exporter tests including the sentinel-token scan
- [ ] CLI failure-isolation test
- [ ] Phase 4 verification

## Phase 5: Documentation and manual check

Requirements: REQ-7, REQ-2, REQ-3, REQ-5

- [ ] README option, env key, outputs, host mapping, skip reasons, undocumented-endpoint note
- [ ] `skills/prinfo/SKILL.md`
- [ ] `skills/prinfo/references/commands.md`, `outputs.md`, `troubleshooting.md`
- [ ] Markdown lint
- [ ] Manual run against a real PR with Copilot review sessions
- [ ] Phase 5 verification
