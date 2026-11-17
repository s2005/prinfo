# AC-10 Manual Run Against a PR With Copilot Review Sessions Not Performed

## Finding

AC-10 needs a manual run against a real PR that has Copilot code review sessions. No such PR was available in this run. None of the PRs of this repository has a Copilot review, so the run could not show a non-empty `findings.json` from live data.

## Evidence

- `verification.md`, Phase 5, "Manual run"; `PRD.md` AC-10.
- A substitute run against PR #2 of this repository on `github.com`, with output outside the repository, exited 0. The manifest showed `copilot_api_host` = `api.githubcopilot.com`, `mode_skip` = `null` and `counts.listed` = 0. That confirms the `github.com` host mapping and the bearer-token call against the live endpoint, which `verification.md` lists as optional. The token scan of the output printed `token absent`.
- Parsing and findings extraction are covered offline by `tests/test_session_log.py` and `tests/test_exporter.py::test_agent_sessions_log_is_byte_identical_and_findings_written`, using the synthetic fixture `tests/fixtures/agent_session_log.sse`.

## Effect

The parser is verified only against a synthetic log modelled on the shape observed during planning (`open_questions.md` Q2, Q3), not against a live review session. The `<tenant>.ghe.com` mapping is unit-tested but was not exercised live in this run.

## Status

Accepted by the user as a known gap on 2026-11-17.

## Next step

Run the Phase 5 manual command from `verification.md` against a PR that has Copilot review sessions, then the token scan. Tick AC-10 once the run writes a non-empty `findings.json`.
