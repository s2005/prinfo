# Open Questions: Export Copilot Agent Sessions for a PR

## Q1: What is the scope of this task inside prinfo?

- **Why it matters**: The originating proposal covered two things: an exporter that pulls Copilot agent sessions (Copilot code review passes, coding-agent runs) for a PR, and changes to a separate PR-review skill that consumes them (pending reviews with inline comments, suggestion blocks, thread replies, reviewer ensembles). Only the first is exporter work; the second lives outside this repository.
- **Options**: (a) exporter mode plus updates to the bundled `skills/prinfo` skill and README; (b) (a) plus a Copilot review request (`request_copilot_review`) and a wait-for-completion poll; (c) exporter mode only, no skill changes.
- **Recommended**: (a) - prinfo stays a read-only exporter. Requesting a review is a write to the PR, which no current mode performs, and waiting changes the tool from "export what exists" to "orchestrate". The bundled skill must document the new mode, as it does every other mode.
- **Answer**: (a) - decided by user.

## Q2: How are a PR's agent sessions discovered?

- **Why it matters**: The documented REST API (`GET /agents/repos/{owner}/{repo}/tasks`) is the obvious choice, but it decides whether the export is complete.
- **Options**: (a) documented `agents/repos/{owner}/{repo}/tasks`, filtered by the `pull` artifact; (b) the Copilot API endpoint `GET <copilot-api>/agents/sessions/resource/pull/{pr_database_id}`.
- **Recommended**: (b).
- **Answer**: (b) - decided by a probe on a data-residency tenant. The documented repository task list returned zero tasks, and the user task list did not contain the Copilot code review task, so review sessions are not discoverable through (a). Endpoint (b) returned every session of the PR, one per review pass, with `agent_slug`, `event_type`, `resource_number` and `state`. `{pr_database_id}` is the `id` field of `GET repos/{owner}/{repo}/pulls/{n}`, not the PR number. Endpoint (b) is undocumented, so the analysis records it as a risk.

## Q3: How does prinfo call the Copilot API, given that every call so far goes through `gh`?

- **Why it matters**: `GhCli._run_command` (`src/prinfo/gh.py:408`) shells out to `gh` for every request. The session and log endpoints live on a different host from the GitHub REST API.
- **Options**: (a) `gh api <full-url>`; (b) `gh api <full-url> -H "Authorization: Bearer <token>"`; (c) Python `urllib.request` with a token obtained from `gh auth token --hostname <host>` (or `--gh-token` / `PRINFO_GH_TOKEN` when given), no new dependency; (d) shell out to `curl`.
- **Recommended**: (c).
- **Answer**: (c) - (a) was ruled out by a probe: `gh api` against the Copilot API host returns HTTP 400 `Authorization header is badly formatted`, because `gh` sends its own token scheme. A bearer token from `gh auth token` returned HTTP 200 on the same endpoint. (b) puts the token on a process command line, which other processes can read. (d) adds an external binary for one call. (c) keeps the token in memory only and honours the existing `--gh-token` and `--gh-config-dir` options. The token is never logged, written to a manifest or included in an error message.

## Q4: How is the Copilot API host chosen?

- **Why it matters**: The host differs by deployment, and a wrong host fails every call in this mode.
- **Options**: (a) derive it from `--gh-host`: `github.com` maps to `api.githubcopilot.com`, `<tenant>.ghe.com` maps to `copilot-api.<tenant>.ghe.com`, and any other host (GitHub Enterprise Server) skips the mode with a reason code; (b) (a) plus a `--copilot-api-url` override option and `PRINFO_COPILOT_API_URL` env key; (c) require the URL explicitly.
- **Recommended**: (a) - it covers both deployments that offer Copilot agents and adds no second option to keep in step. The data-residency mapping was confirmed by probe; the `github.com` mapping comes from GitHub's own CLI and docs. An override can follow if a third shape appears.
- **Answer**: (a) - decided by user.

## Q5: What does the export write?

- **Why it matters**: One review session log measured about 425 KB of server-sent events. The raw form is faithful but unreadable; a parsed form is what a reviewer or an agent needs.
- **Options**: (a) raw log only; (b) per session: `session.json` (metadata), `log.sse` (raw stream), `transcript.md` (assistant text and tool calls in order) and `findings.json` (the code review's stored comments with file, line range, type, suggested fix or skip reason), plus a top-level `agent-sessions.json` manifest; (c) (b) without the raw log.
- **Recommended**: (b) - the raw log keeps the export faithful when the event format changes and the parser misses something; the parsed files are what gets read. All files go under `agent-sessions/<session_id>/`.
- **Answer**: (b) - decided by user.

## Q6: Which sessions are exported?

- **Why it matters**: A PR reviewed twice has two review sessions; a PR can also carry coding-agent sessions.
- **Options**: (a) every session for the PR, any agent type, ordered by creation time; (b) only the latest session; (c) only Copilot code review sessions.
- **Recommended**: (a) - earlier passes hold findings that later passes only refer to as already reported. `findings.json` is written only for sessions whose log contains stored review comments; other sessions still get metadata, raw log and transcript.
- **Answer**: (a) - decided by user.

## Q7: What happens to identifying and internal data in session metadata?

- **Why it matters**: Session metadata embeds a serialized `event_identifiers` blob holding the requesting user's login, a user tracking id, request ids, the seat access type and the full internal review configuration (model names, budgets, thresholds). Exports are often attached to tickets or handed to other tools.
- **Options**: (a) write metadata as returned; (b) write a curated subset by default (session id, agent, state, timestamps, model, review pass, head SHA, last reviewed head revision, review effort level) and drop the identifying fields and the settings blob; (c) (b) plus an option to include the full blob.
- **Recommended**: (b) - the curated subset is what review tooling needs. The raw log is kept as returned (Q5), so nothing is lost locally, and the manifest stays safe to share. An include-everything option can follow on request.
- **Answer**: (b) - decided by user.

## Q8: What are the CLI option and env key names?

- **Why it matters**: Each export mode has a `--export-*` flag and a `PRINFO_EXPORT_*` env key resolved in `resolve_config` (`src/prinfo/config.py:43`), and `--skip-check-logs` must accept the new mode as a valid companion (`src/prinfo/config.py:56`).
- **Options**: (a) `--export-agent-sessions` and `PRINFO_EXPORT_AGENT_SESSIONS`; (b) `--export-copilot-sessions` and `PRINFO_EXPORT_COPILOT_SESSIONS`.
- **Recommended**: (a).
- **Answer**: (a) - decided by reading `src/prinfo/config.py` and `src/prinfo/cli.py:35`. The name matches the API's own term (`agents/sessions`) and the existing `--export-*` pattern, and it does not tie the flag to one agent type.

## Q9: How do failures in the new mode interact with the other modes?

- **Why it matters**: The endpoints are undocumented and may change; a failure must not lose the check-log or comment export of the same run.
- **Options**: (a) the mode fails like any other, and `main` isolates it per mode; (b) a dedicated fatal error.
- **Recommended**: (a).
- **Answer**: (a) - decided by reading `src/prinfo/cli.py:120-140`: each mode runs in its own `try` block, and the run fails only when no mode produced a result. HTTP 401, 403 and 404 from the Copilot API become a skip with a reason code (no Copilot access, or no sessions), not a crash.

## Q10: Does the new option require a version bump?

- **Why it matters**: The user's rules require a bump in the same change whenever input parameters change, for non-fork repositories owned by the `s2005` account.
- **Options**: (a) minor bump `0.4.0` to `0.5.0` via `pyproject.toml` and `uv lock`; (b) patch bump.
- **Recommended**: (a).
- **Answer**: (a) - decided by reading `pyproject.toml:3`, the `origin` remote (owner `s2005`, no `upstream`) and `git config user.name`. An added option is an additive change, which bumps minor while the version is `0.x`.

## Q11: Is review-thread resolution state already available for consumers?

- **Why it matters**: The proposal relies on resolved and outdated thread state so a reviewer does not raise a settled thread again.
- **Options**: (a) already exported; (b) needs adding.
- **Recommended**: (a).
- **Answer**: (a) - decided by reading `src/prinfo/gh.py:22-27` and `src/prinfo/gh.py:247`: `--export-comments` already queries `reviewThreads` with `isResolved` and `isOutdated`. Nothing to add in this task.

## Resolution Summary

| ID | Status | Carried by |
| -- | ------ | ---------- |
| Q1 | Answered | Non-Requirements, REQ-7 |
| Q2 | Answered | REQ-2 |
| Q3 | Answered | REQ-3 |
| Q4 | Answered | REQ-3 |
| Q5 | Answered | REQ-4, REQ-5 |
| Q6 | Answered | REQ-2 |
| Q7 | Answered | REQ-4 |
| Q8 | Answered | REQ-1 |
| Q9 | Answered | REQ-6 |
| Q10 | Answered | REQ-8 |
| Q11 | Answered | Non-Requirements |
