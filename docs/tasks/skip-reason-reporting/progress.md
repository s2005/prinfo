# Progress: Skip Reason Severity Reporting

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

## Phase 1: Commit finished commit-export work

Requirements: REQ-1, REQ-2

- [x] `commits-manifest.json` per-commit records embed the full `skipped`
      array (`_CommitFolderResult`, `src/prinfo/exporter.py`).
- [x] `CommitExportResult.skipped_file_reasons` breakdown implemented.
- [x] `ACTIONABLE_COMMIT_SKIP_REASONS` implemented and read by the
      commit-file branch of `_log_mode_summaries`.
- [x] WARNING/INFO split implemented for the commit-file summary
      (`src/prinfo/cli.py:195-207`).
- [x] Four supporting tests (two regression, two positive-path) added.
- [x] `README.md` and `skills/prinfo/references/outputs.md` updated for the
      commit-file skip-reason sections.
- [x] Stage and commit the six affected files as one commit, per Q6 - done as
      `2bedef1`, "Explain skipped commit files and split their severity (#4)",
      body `Closes #3`. Not repeated in this run; see `notes.md` drift D1.
- [x] Run `uv run pytest`, `uv run ruff check src tests`,
      `npx pyright src/prinfo/exporter.py src/prinfo/cli.py` and
      `npx markdownlint-cli2 "**/*.md" "#node_modules"` against the commit -
      re-run at the start of this run against `2bedef1`: 76 passed, `ruff`
      clean, `pyright` 0 errors, `markdownlint-cli2` clean.

## Phase 2: Shared severity helper

Requirements: REQ-5

- [x] Add `_log_skip_severity` to `src/prinfo/cli.py`.
- [x] Route the commit-file branch of `_log_mode_summaries` through
      `_log_skip_severity`.
- [x] Confirm the four existing commit-file severity tests pass unchanged.
- [x] Add direct unit tests for `_log_skip_severity` covering mixed,
      actionable-only, benign-only and zero-total breakdowns.
- [x] Run `uv run pytest tests/test_cli.py` and `uv run ruff check src tests` -
      20 passed in `tests/test_cli.py`, 80 passed overall (up from 76), `ruff`
      clean, `pyright` 0 errors.

## Phase 3: Check-log severity split

Requirements: REQ-3, REQ-4

- [x] Add `ACTIONABLE_CHECK_SKIP_REASONS` to `src/prinfo/exporter.py`.
- [x] Add `skipped_check_reasons` to `ExportResult`.
- [x] Populate `skipped_check_reasons` in `export_pr_check_logs` via
      `collections.Counter`.
- [x] Change the `unsupported_check_type` per-item log from WARNING to INFO.
- [x] Leave the `missing_log_content` per-item log at WARNING.
- [x] Route the check-log branch of `_log_mode_summaries` through
      `_log_skip_severity` with the check-log actionable set and messages.
- [x] Add exporter tests for the `skipped_check_reasons` breakdown.
- [x] Add exporter tests asserting per-item log level via `caplog`.
- [x] Add CLI tests for the mixed-reason WARNING/INFO split.
- [x] Add a CLI test proving a benign-only check-log result produces no
      WARNING.
- [x] Run `uv run pytest tests/test_exporter.py tests/test_cli.py`,
      `uv run ruff check src tests` and
      `npx pyright src/prinfo/exporter.py src/prinfo/cli.py` - 85 passed
      overall (up from 80), `ruff` clean, `pyright` 0 errors.
- [x] Add a CLI test that patches `_log_skip_severity` once and asserts both
      the check-log and commit-file branches call it (AC-5).

## Phase 4: Comment-source finding and guard test

Requirements: REQ-6

- [x] Confirm no production code change is needed in `export_pr_comments` or
      in the `skipped_sources` branch of `_log_mode_summaries`.
- [x] Add a test driving `export_pr_comments` through all four source
      failures and asserting every recorded `reason_code` is
      `"source_unavailable"`.
- [x] Run `uv run pytest tests/test_exporter.py -k comments` - passes;
      89 tests overall, up from 85, which is exactly the four new
      parametrized cases.
- [x] Confirm `git diff src/prinfo/exporter.py src/prinfo/cli.py` shows no
      change from the end of Phase 3 - `git diff --stat -- src` is empty.

## Phase 5: Documentation

Requirements: REQ-7

- [x] Update `README.md` with the check-log severity split.
- [x] Update `skills/prinfo/references/outputs.md`'s
      `## How to explain skipped checks` section with the actionable/benign
      classification and the per-item log-level change.
- [x] Run `npx markdownlint-cli2 "**/*.md" "#node_modules"` - 55 files,
      0 errors.
- [x] Cross-check every reason code and log level named in the docs against
      `src/prinfo/exporter.py` - `unsupported_check_type` is logged by
      `LOGGER.info` and is absent from `ACTIONABLE_CHECK_SKIP_REASONS`;
      `missing_log_content` is logged by `LOGGER.warning` and is the set's
      only member. Both summary message strings match `src/prinfo/cli.py`.
