# PRD: Export PR Comments and Commit Log

## Objective

Add two export modes to `prinfo` so a pull request's full review discussion and its commit history can be saved to disk without downloading every changed file. `--export-comments` writes the PR discussion, inline review comments, review verdicts and per-thread resolved state as both structured JSON and a readable Markdown transcript. `--export-commit-log` writes commit metadata alone, reusing the commit payload already fetched when the per-commit file export runs in the same invocation.

## Background

`prinfo` currently reaches GitHub through five `gh` calls in `src/prinfo/gh.py`: `list_pr_checks`, `list_pr_commits`, `get_commit_details`, `download_job_log` and `download_commit_file`. Nothing in the client touches comments, so a PR's review discussion cannot be exported at all.

Commit history is captured today, but only as a by-product of `--export-commit-files`. That flag walks `repos/<owner>/<repo>/pulls/<n>/commits`, writes the full `PrCommit` record (sha, short sha, message headline, full message, authored date, committed date, url) into `commits-manifest.json` and `commits/<sha>/_commit.json`, and then downloads every changed file blob for every commit (`src/prinfo/exporter.py:155`). A user who wants only the commit history pays for the whole file download.

Both gaps are addressed by the paginated helper the client already has. `_run_paginated_json` (`src/prinfo/gh.py:188`) handles `--paginate --slurp` and page flattening, so the three REST comment endpoints and the commit list need no new pagination logic. Review-thread resolved state is the exception: REST does not expose it, so it needs a GraphQL query against `repository.pullRequest.reviewThreads`.

## Requirements

### REQ-1: gh client exposes the three REST comment sources

`GhCli` gains three methods, each returning a frozen dataclass list built from `_run_paginated_json`:

- `list_pr_issue_comments(repo, pr_number)` reads `repos/<owner>/<repo>/issues/<n>/comments` and returns `IssueComment` records carrying `comment_id`, `author`, `author_type`, `body`, `created_at`, `updated_at`, `url`.
- `list_pr_review_comments(repo, pr_number)` reads `repos/<owner>/<repo>/pulls/<n>/comments` and returns `ReviewComment` records carrying `comment_id`, `author`, `author_type`, `body`, `created_at`, `updated_at`, `url`, `path`, `line`, `original_line`, `side`, `commit_id`, `in_reply_to_id`, `diff_hunk`, `pull_request_review_id`.
- `list_pr_reviews(repo, pr_number)` reads `repos/<owner>/<repo>/pulls/<n>/reviews` and returns `PullRequestReview` records carrying `review_id`, `author`, `author_type`, `body`, `state`, `submitted_at`, `url`, `commit_id`.

A missing or non-object payload entry raises `GhCliError` with the endpoint named, matching `_parse_pr_commit`. A missing optional field resolves to `None` rather than an empty string, and an absent `user` object yields `author=None` without raising.

### REQ-2: `--export-comments` writes `comments.json` covering all three sources

The exporter writes `comments.json` into the output directory with top-level keys `repo`, `pr_number`, `issue_comments`, `review_comments`, `reviews`, `review_threads`, `counts` and `skipped_sources`. Every record is written verbatim as returned - no bot filtering, no dropping of empty review bodies - with `author` and `author_type` present on every entry so a consumer can filter. `counts` reports the number of records exported per source.

### REQ-3: `--export-comments` writes a `comments.md` transcript

Alongside the JSON, the exporter renders `comments.md` from the same in-memory records, ordered by timestamp across all sources, with:

- a title line naming the repo and PR number,
- one section per entry headed by author, source kind, timestamp and, for reviews, the review state,
- for an inline review comment, its `path` and line reference in the heading and its resolved state when known,
- the comment body reproduced verbatim beneath the heading.

An entry with no timestamp sorts last rather than raising. The file is written with `encoding="utf-8"` and never contains a machine-specific absolute path.

### REQ-4: `--export-commit-log` writes `commit-log.json` from a shared fetch

`--export-commit-log` writes `commit-log.json` with `repo`, `pr_number`, `commit_count` and a `commits` array of the full `PrCommit` records, and downloads no file blobs. When `--export-commit-files` runs in the same invocation, the commit list is fetched once and both outputs are produced from it, so `repos/<owner>/<repo>/pulls/<n>/commits` is requested exactly once per run. `commits-manifest.json` keeps its current shape and content unchanged.

### REQ-5: Config surface for both flags, with the export guard relaxed

`--export-comments` and `--export-commit-log` are added to the parser with `PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG` as their env counterparts, resolved through the existing `_resolve_bool` precedence where a CLI flag wins and an env value is truthy for `1`, `true`, `yes` or `on`. `AppConfig` gains `export_comments` and `export_commit_log` fields. The guard at `src/prinfo/config.py:52` is widened so `--skip-check-logs` is satisfied by any one of `export_commit_files`, `export_comments` or `export_commit_log`, and its error message names all three. `--skip-check-logs` with no export mode at all still raises `ConfigurationError`.

### REQ-6: Per-source and per-mode failure isolation

A `GhCliError` from one comment endpoint does not abort the other two: the failure is recorded in `skipped_sources` with the source name, the reason string and a `reason_code`, matching the skipped-record convention already used for checks and commit files. A comment export in which every source failed raises `ExportError`. In `main`, the two new modes are wrapped the same way the existing two are (`src/prinfo/cli.py:80-95`): each records its own error, a failure in one does not prevent the others from running, and the run exits non-zero only when no mode produced a result.

### REQ-7: Review-thread resolved state via GraphQL

`GhCli.list_pr_review_threads(repo, pr_number)` issues a GraphQL query against `repository.pullRequest.reviewThreads`, paginating with `$endCursor` and `pageInfo { hasNextPage endCursor }`, and returns `ReviewThread` records carrying `thread_id`, `is_resolved`, `is_outdated` and the `comment_ids` in the thread. The exporter maps each thread's `comment_ids` onto the REST review comments by comment id, so every entry in `review_comments` carries `is_resolved` and `thread_id` (both `None` when no thread matched). Threads are also written under the `review_threads` key of `comments.json`. A GraphQL failure is recorded in `skipped_sources` and leaves the REST comment export intact with `is_resolved` unset.

### REQ-8: Documentation records both new flags

`README.md` gains both flags in the quick-start examples, both env keys in the supported-keys list, and a description of `comments.json`, `comments.md` and `commit-log.json` under `## Output`. The relaxed `--skip-check-logs` rule is restated where the current commit-only sentence sits. `skills/prinfo/SKILL.md`, `skills/prinfo/references/commands.md` and `skills/prinfo/references/outputs.md` are updated so the agent skill describes the new modes and their output files.

## Non-Requirements

- No comment filtering, bot exclusion or `--comments-exclude-bots` flag - records are exported verbatim, per Q6 in `open_questions.md`.
- No posting, editing, resolving or replying to comments; the tool stays read-only.
- No export of PR description, labels, assignees, requested reviewers or timeline events.
- No commit diffs or patches in `commit-log.json`; it carries metadata only, and `--export-commit-files` remains the way to get file content.
- No change to the shape or content of `manifest.json`, `commits-manifest.json` or `commits/<sha>/_commit.json`.
- No new output format beyond JSON and Markdown - no HTML, no CSV.

## Acceptance Criteria

- **AC-1** - `GhCli.list_pr_issue_comments`, `list_pr_review_comments` and `list_pr_reviews` each parse a fake paginated payload into the documented dataclass fields, and each raises `GhCliError` naming the endpoint on a non-object entry (REQ-1)
- **AC-2** - A comment export run writes `comments.json` whose `issue_comments`, `review_comments` and `reviews` arrays hold every record from the fake client, with `author` and `author_type` on each and per-source `counts` (REQ-2)
- **AC-3** - The same run writes `comments.md` whose sections appear in timestamp order across all three sources, with an untimestamped entry placed last and no exception raised (REQ-3)
- **AC-4** - `--export-commit-log` alone writes `commit-log.json` with the full `PrCommit` fields and downloads no file blobs; with `--export-commit-files` also set, both outputs are written and the commits endpoint is requested exactly once (REQ-4)
- **AC-5** - `build_parser` accepts `--export-comments` and `--export-commit-log`, and `resolve_config` maps `PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG` onto them with the CLI flag overriding the env value (REQ-5)
- **AC-6** - `--skip-check-logs` is accepted with any single one of the three export modes and still raises `ConfigurationError` naming all three when none is set (REQ-5)
- **AC-7** - A `GhCliError` from one comment endpoint leaves the other two exported and records the failure under `skipped_sources` with a `reason_code`, and a run where every source failed raises `ExportError` (REQ-6)
- **AC-8** - `main` returns 0 when one of several requested modes fails and another succeeds, and returns 1 when every requested mode fails (REQ-6)
- **AC-9** - `list_pr_review_threads` parses a paginated GraphQL payload into `ReviewThread` records, and the exporter sets `is_resolved` and `thread_id` on each matching review comment while leaving unmatched comments at `None` (REQ-7)
- **AC-10** - A GraphQL failure records a `review_threads` entry in `skipped_sources` while `comments.json` still contains all three REST sources (REQ-7)
- **AC-11** - `README.md` documents both flags, both env keys and all three new output files, and `markdownlint-cli2` reports no findings on the changed Markdown (REQ-8)
- **AC-12** - `uv run ruff check .` and `uv run pytest` both pass on the finished branch (REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6, REQ-7)

## Deliverables

| Deliverable | Type |
| ----------- | ---- |
| src/prinfo/gh.py | Update |
| src/prinfo/config.py | Update |
| src/prinfo/cli.py | Update |
| src/prinfo/exporter.py | Update |
| `src/prinfo/__init__.py` | Update |
| tests/test_gh.py | Update |
| tests/test_config.py | Update |
| tests/test_cli.py | Update |
| tests/test_exporter.py | Update |
| README.md | Update |
| skills/prinfo/SKILL.md | Update |
| skills/prinfo/references/commands.md | Update |
| skills/prinfo/references/outputs.md | Update |
