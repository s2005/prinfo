# Notes: Spec-to-Code Drift

## Drifts

### D1: The version is defined in two places

- **Spec:** `PRD.md` REQ-8 and `implementation_plan.md` Phase 1 bump `pyproject.toml` and run `uv lock`, and expect `uv run prinfo --version` to print `prinfo 0.5.0`.
- **Code:** `src/prinfo/__init__.py:3` hard-codes `__version__ = "0.4.0"`, and `--version` prints that value (`src/prinfo/cli.py:9`, `src/prinfo/cli.py:43`).
- **Difference:** bumping `pyproject.toml` alone leaves `prinfo --version` at `0.4.0`, so AC-9 cannot pass. Every earlier bump (`13e7e38`, `cbf07b8`, `57622a1`) changed both files.

### D2: The manifest has no key for a mode-level skip

- **Spec:** `PRD.md` REQ-4 lists the manifest keys `repo`, `pr_number`, `copilot_api_host`, `sessions`, `skipped_sessions`, `counts`. `implementation_plan.md` Phase 4 steps 2 and 3 write "the manifest with a mode-level skip" (`unsupported_host`, `no_copilot_access`, `no_sessions_endpoint`).
- **Code:** none yet; `skipped_sessions` holds per-session records, so a mode-level skip has nowhere to go.
- **Difference:** the spec requires a mode-level skip to be recorded, but its key list has no place for it.

### D3: Which host the Copilot API host is derived from

- **Spec:** `PRD.md` REQ-3 derives the host "from the GitHub host"; `implementation_plan.md` Phase 2 names the input `gh_host`.
- **Code:** `--repo` may carry its own host (`HOST/OWNER/REPO`, `src/prinfo/gh.py:441`), and every other API call targets `repo_ref.host` (`src/prinfo/gh.py:208-210`), which equals `--gh-host` only when the repo has no host part.
- **Difference:** ambiguous; a repo host that differs from `--gh-host` would be mapped from one host and queried for a PR on another.

### D4: `AgentSessionExportResult` lacks the fields the summary needs

- **Spec:** `implementation_plan.md` Phase 4 gives the result `manifest_path`, `exported_sessions`, `skipped_sessions` and `findings_count`, and asks `_log_mode_summaries` to log the counts with `_log_skip_severity`, at `WARNING` for access and host skips.
- **Code:** `_log_skip_severity` needs a per-reason breakdown (`src/prinfo/cli.py:231-251`), and every other summary line names the repo, PR and output directory (`src/prinfo/cli.py:157-163`).
- **Difference:** the listed fields carry neither the per-reason breakdown nor the mode-level skip reason, so the specified logging cannot be produced from them.

### D5: Other discovery failures are unspecified

- **Spec:** `PRD.md` REQ-6 covers HTTP 401, 403 and 404 on discovery only.
- **Code:** `main` isolates a failing mode only for `ExportError`, `GhCliError` and `OSError` (`src/prinfo/cli.py:133`). A `CopilotApiError` for HTTP 500 or a network failure is none of these.
- **Difference:** such a failure would escape `main` as a traceback and stop the other modes, contrary to REQ-6's isolation intent.

## Candidate Solutions

### 01: Amend the spec where it is silent, follow the project's conventions in code

- **Approach:** D1, bump `src/prinfo/__init__.py` with `pyproject.toml`, as every earlier bump did. D2, add a manifest key `mode_skip` (`null`, or `{reason_code, reason}`). D3, derive the Copilot host and the `gh auth token --hostname` value from the resolved repo host, which defaults to `--gh-host`. D4, give the result `repo`, `pr_number`, `output_dir`, `skipped_session_reasons` and `mode_skip_reason_code`. D5, turn any other discovery `CopilotApiError` into `ExportError`.
- **Scope:** `src/prinfo/__init__.py` plus files the plan already touches; `PRD.md` REQ-4 gains one key.
- **Pros:** every acceptance criterion becomes reachable; matches the existing modes' patterns; no new option.
- **Cons:** one manifest key beyond the PRD list.
- **Risk:** low.

### 02: Follow the spec text literally

- **Approach:** bump `pyproject.toml` only, record mode-level skips in `skipped_sessions`, map from `--gh-host`, keep the four result fields, leave other errors unhandled.
- **Scope:** as planned.
- **Pros:** no spec change.
- **Cons:** AC-9 fails; a mode-level skip masquerades as a session; a 500 crashes the run.
- **Risk:** high.

### 03: Derive `__version__` from package metadata

- **Approach:** as 01, but replace the literal in `__init__.py` with `importlib.metadata.version("prinfo")`.
- **Scope:** adds a behaviour change to version reporting.
- **Pros:** one place to bump in future.
- **Cons:** an improvement no ticket asks for (`rules/jira-scope.md`); changes behaviour when run from a source tree without installed metadata.
- **Risk:** medium.
