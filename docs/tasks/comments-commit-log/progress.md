# Progress: Export PR Comments and Commit Log

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

## Phase 1: Config and CLI surface

Requirements: REQ-5

- [x] Add `export_comments` and `export_commit_log` to `AppConfig`.
- [x] Resolve both from `PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG` via `_resolve_bool`.
- [x] Widen the `--skip-check-logs` guard to accept any one of the three export modes.
- [x] Rewrite the guard error message to name all three flags and env keys.
- [x] Add `--export-comments` and `--export-commit-log` to `build_parser`.
- [x] Add config tests for defaults, env resolution and CLI-over-env precedence.
- [x] Add config tests for the relaxed guard, one per accepted mode plus the rejection case.
- [x] Add parser tests for both flags.
- [x] Run `uv run pytest tests/test_config.py tests/test_cli.py`.

## Phase 2: gh client comment access

Requirements: REQ-1, REQ-7

- [x] Add `IssueComment`, `ReviewComment`, `PullRequestReview` and `ReviewThread` dataclasses.
- [x] Add `_parse_issue_comment`, `_parse_review_comment` and `_parse_review`.
- [x] Add `list_pr_issue_comments` over `issues/<n>/comments`.
- [x] Add `list_pr_review_comments` over `pulls/<n>/comments`.
- [x] Add `list_pr_reviews` over `pulls/<n>/reviews`.
- [x] Add `_run_graphql_paginated` handling both single-document and multi-document output.
- [x] Add `list_pr_review_threads` selecting `isResolved`, `isOutdated` and `comments.nodes.databaseId`.
- [x] Add parser tests for each REST method over a two-page payload.
- [x] Add tests for malformed entries and a missing `user` object.
- [x] Add a paginated GraphQL parse test and a `--hostname` test for an enterprise repo.
- [x] Run `uv run pytest tests/test_gh.py` and `uv run ruff check src tests`.

## Phase 3: Comment export

Requirements: REQ-2, REQ-3, REQ-6, REQ-7

- [x] Add `CommentExportResult`.
- [x] Add `export_pr_comments` calling all four sources with per-source error isolation.
- [x] Add `_skipped_source_record` following the existing skipped-record convention.
- [x] Raise `ExportError` when every source failed.
- [x] Map review threads onto review comments by comment id.
- [x] Write `comments.json` with all documented keys and per-source counts.
- [x] Add `_render_comments_markdown` with timestamp ordering and untimestamped entries last.
- [x] Write `comments.md` with `encoding="utf-8"`.
- [x] Add exporter tests for the JSON contents and counts.
- [x] Add exporter tests for transcript ordering.
- [x] Add exporter tests for one-source failure and total failure.
- [x] Add exporter tests for thread mapping, matched and unmatched.
- [x] Add an exporter test for an isolated GraphQL failure.
- [x] Run `uv run pytest tests/test_exporter.py`.

## Phase 4: Commit log export

Requirements: REQ-4

- [x] Add `CommitLogExportResult`.
- [x] Add the shared commit-list cache and route `export_pr_commit_files` through it.
- [x] Add `export_pr_commit_log` writing `commit-log.json` and downloading nothing.
- [x] Confirm `commits-manifest.json` and `_commit.json` are unchanged.
- [x] Add a test that the commit-log export downloads no files.
- [x] Add a counting-fake test asserting exactly one `list_pr_commits` call when both commit modes run.
- [x] Run `uv run pytest tests/test_exporter.py`.

## Phase 5: Orchestration

Requirements: REQ-6

- [x] Replace the parallel result and error locals in `main` with a per-mode record list.
- [x] Run each requested mode in its own `try` with per-mode error recording.
- [x] Raise only when no mode produced a result.
- [x] Log a per-mode summary covering all four modes.
- [x] Bump the version to `0.4.0` in `src/prinfo/__init__.py` and `pyproject.toml`, and run `uv lock`.
- [x] Add CLI tests for partial-failure exit 0 and total-failure exit 1.
- [x] Update the `--version` test to `0.4.0`.
- [x] Run `uv run pytest` and `uv run ruff check .`.

## Phase 6: Documentation and skill

Requirements: REQ-8

- [x] Update `README.md` with both flags, both env keys, the three new output files and the relaxed skip rule.
- [x] Update `skills/prinfo/SKILL.md`.
- [x] Update `skills/prinfo/references/commands.md`.
- [x] Update `skills/prinfo/references/outputs.md`.
- [x] Update `skills/prinfo/references/troubleshooting.md` with the new failure modes.
- [x] Run `markdownlint-cli2 "**/*.md" "#node_modules"`.

## Phase 7: Commit authorship

Requirements: REQ-9

- [x] Add the six authorship fields to `PrCommit` in grouped order, every field required.
- [x] Populate them in `_parse_pr_commit` through `_optional_str`.
- [x] Take `author_login` and `committer_login` from the top-level objects and tolerate a null.
- [x] Extend the paginated commit parse test to assert all six fields.
- [x] Add a test for a null top-level author yielding `author_login` of `None`.
- [x] Add a test that an absent author object resolves every field to `None`.
- [x] Update the six `PrCommit(...)` constructions in `tests/test_exporter.py`.
- [x] Assert the fields reach `commit-log.json`, `commits-manifest.json` and `_commit.json`.
- [x] Update the commit field list in `README.md`.
- [x] Update the commit field list in `skills/prinfo/references/outputs.md`.
- [x] Run `uv run pytest`, `uv run ruff check .` and `markdownlint-cli2 "**/*.md" "#node_modules"`.

## Follow-Ups Found

Found while running the Phase 6 documentation drift check, and deliberately left
alone because no requirement in this task covers it:

- `PRINFO_ENV_FILE` is read by `_resolve_env_file` in `src/prinfo/config.py` but
  is absent from the supported-env-keys list in `README.md` and in
  `skills/prinfo/references/commands.md`. The gap predates this task and this
  task does not make it worse, so it needs its own ticket rather than riding
  along with this one.
- `skills/prinfo/references/commands.md` lists supported env keys without
  `PRINFO_EXPORT_COMMIT_FILES` and `PRINFO_SKIP_CHECK_LOGS`. Same reasoning: the
  omission predates this task.
- The `repos/<owner>/<repo>/pulls/<n>/commits` endpoint behind
  `GhCli.list_pr_commits` returns at most 250 commits, so both
  `commits-manifest.json` and the new `commit-log.json` silently truncate a
  larger PR and report `commit_count: 250`. The call and the cap arrived in
  `cbf07b8`, the merge base of this branch, and this task reuses that fetch
  rather than adding a new one, so it does not make the gap worse. Choosing
  between the general commits endpoint and an explicit failure changes
  `--export-commit-files` behaviour and needs its own ticket. Raised by Codex
  on PR #2, see `analysis_4_commits_endpoint_250_limit.md`.

## Review Feedback (PR #2)

- [x] P1: Catch GitHub errors inside each export mode (fixed - the per-mode loop in `main` now records `GhCliError` alongside `ExportError`, so a `gh` API or permission failure in one mode no longer aborts the remaining requested modes)
- [x] P2: Isolate filesystem errors between export modes (fixed - the per-mode loop in `main` now records `OSError` alongside `ExportError` and `GhCliError`, so a filesystem failure in one mode no longer aborts the remaining requested modes)
- [x] P2: Preserve empty comment bodies in the transcript (fixed - `_comment_body` now reserves the `(no body)` placeholder for `None` and renders an empty body as an empty section, matching `comments.json`)
- [-] P4: Handle pull requests with more than 250 commits (rejected - the 250-commit cap predates this branch in `GhCli.list_pr_commits` and already truncates `commits-manifest.json` on `main`; recorded as a follow-up ticket)
