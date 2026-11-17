# Solution 01: Amend the Spec Where It Is Silent

## Chosen Approach

Option 01 from `notes.md`: follow the project's existing conventions in code, and amend the spec only where it says nothing or contradicts itself.

| Drift | Resolution |
| ----- | ---------- |
| D1 | Bump `src/prinfo/__init__.py` together with `pyproject.toml` and `uv.lock` |
| D2 | Manifest key `mode_skip`: `null`, or `{"reason_code": ..., "reason": ...}`; `PRD.md` REQ-4 amended |
| D3 | Copilot host and `gh auth token --hostname` both use the resolved repo host, which defaults to `--gh-host` |
| D4 | `AgentSessionExportResult` also carries `repo`, `pr_number`, `output_dir`, `skipped_session_reasons` and `mode_skip_reason_code` |
| D5 | Any other `CopilotApiError` on discovery becomes `ExportError`, so `main` isolates it |

## Why It Beats the Rejected Options

- **Over 02:** 02 leaves AC-9 unreachable, mixes a mode-level skip into the per-session list, and lets an HTTP 500 stop the other modes of the run.
- **Over 03:** 03 fixes D1 by changing how the version is computed, which no requirement asks for; the literal bump matches the repository's history.

## Files to Change

Those in `implementation_plan.md`, plus `src/prinfo/__init__.py` (D1) and `PRD.md` REQ-4 (D2).

## Implementation Outline

1. Phase 1 bumps both version locations.
2. Phase 2 gives `GhCli.auth_token` an optional `host` keyword defaulting to `gh_host`.
3. Phase 4 resolves the repo host first, maps it, and passes it to `auth_token`; writes `mode_skip`; returns the extended result; wraps other discovery errors in `ExportError`.

## Verification

- `uv run prinfo --version` prints `prinfo 0.5.0` (D1).
- Exporter tests assert `mode_skip` for `unsupported_host`, `no_copilot_access` and `no_sessions_endpoint`, and `null` on a normal run (D2).
- An exporter test with `--repo <tenant>.ghe.com/o/r` and default `--gh-host` maps to the tenant host (D3).
- A CLI test checks the summary lines (D4).
- An exporter test turns an HTTP 500 on discovery into `ExportError` (D5).
