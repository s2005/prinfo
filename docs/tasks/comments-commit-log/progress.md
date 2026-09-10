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

## Phase 5: Orchestration and docs

Requirements: REQ-6, REQ-8

- [ ] Replace the parallel result and error locals in `main` with a per-mode record list.
- [ ] Run each requested mode in its own `try` with per-mode error recording.
- [ ] Raise only when no mode produced a result.
- [ ] Log a per-mode summary covering all four modes.
- [ ] Bump `__version__` to `0.4.0`.
- [ ] Update `README.md` with both flags, both env keys, the three new output files and the relaxed skip rule.
- [ ] Update `skills/prinfo/SKILL.md`.
- [ ] Update `skills/prinfo/references/commands.md`.
- [ ] Update `skills/prinfo/references/outputs.md`.
- [ ] Add CLI tests for partial-failure exit 0 and total-failure exit 1.
- [ ] Update the `--version` test to `0.4.0`.
- [ ] Run `uv run pytest`, `uv run ruff check .` and `markdownlint-cli2 "**/*.md" "#node_modules"`.

## Review Feedback

(Section appears when PR review feedback arrives. Each comment gets a checkbox.)
