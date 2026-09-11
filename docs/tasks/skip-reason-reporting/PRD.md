# PRD: Skip Reason Severity Reporting

## Objective

Make every `prinfo` skip summary say whether a skip needs action, for all three
export modes issue #3 names. `commits-manifest.json` must carry the reason for
every skipped commit file without opening a per-commit folder, and the CLI
summary for commit files and check logs must warn only on a skip a user can
act on, logging the rest at INFO. Comment-source skips are checked against the
same expectation and found already correct, so that part closes with a
recorded finding and a guard test rather than a code change.

## Background

Issue #3 describes three things under one root cause: `prinfo` treats every
skip the same way in its summary output, even though the underlying
`reason_code` already distinguishes a skip nobody can do anything about from
one that signals a real failure.

1. `commits-manifest.json` recorded `skipped_files` as a bare count with no
   detail, so a user had to open every `commits/<sha>/_commit.json` to learn
   why a file was skipped.
2. The CLI's commit-file summary warned on any non-zero `skipped_files` count,
   so a PR that only deletes files produced the same `WARNING` line as a PR
   with real download failures.
3. The issue's closing sentence claims `skipped_checks`
   (`src/prinfo/cli.py:167`) and `skipped_sources` (`:180`) share the same
   pattern and are "worth fixing once rather than three times."

Items 1 and 2 are already implemented, tested, verified and merged. They
shipped as commit `2bedef1`, "Explain skipped commit files and split their
severity (#4)", whose body reads `Closes #3`: `commits-manifest.json`
per-commit records now embed the full `skipped` array, and
`ACTIONABLE_COMMIT_SKIP_REASONS = frozenset({"download_failed"})`
(`src/prinfo/exporter.py:429`) drives a severity split in
`src/prinfo/cli.py:195-207` between a WARNING for downloads that failed and an
INFO for files that could never have been downloaded. Four tests cover it, and
the suite is otherwise unchanged: 76 tests passing, `ruff` clean, `pyright`
clean on `src/prinfo/exporter.py` and `src/prinfo/cli.py`, `markdownlint-cli2`
clean.

Reading item 3 against the source shows it is half right. Check-log export
(`src/prinfo/exporter.py:119-144`) produces two reason codes exactly like
commit files: `unsupported_check_type` (the check is not a GitHub Actions job
at all, benign) and `missing_log_content` (a real Actions job returned no
downloadable log, actionable). That half of item 3 is real, uncovered work.
Comment-source export (`src/prinfo/exporter.py:223`, `:232`, `:241`, `:250`)
produces exactly one reason code, `source_unavailable`, at all four call
sites, and it always means a `gh` call failed. There is nothing to split: a
severity split over one code that is always actionable has no benign branch
to route to INFO. The existing unconditional warning in `skipped_sources`
already matches user expectation, so this task's contribution there is a
recorded finding, not a change.

## Requirements

### REQ-1: Commit-manifest skip reasons embedded (status: already implemented)

`_export_commit_folder` returns a `_CommitFolderResult` whose `record` embeds
the full `skipped` array (`path`, `status`, `additions`, `deletions`,
`changes`, `previous_path`, `reason_code`, `reason`) into each commit entry of
`commits-manifest.json`, matching the pattern already used by `manifest.json`
(`skipped`) and `comments.json` (`skipped_sources`). No `commits/<sha>/_commit.json`
lookup is needed to explain a skip.

### REQ-2: Commit-file summary severity split (status: already implemented)

`CommitExportResult` carries `skipped_file_reasons: Mapping[str, int]`, a
per-reason-code breakdown of `skipped_files`.
`ACTIONABLE_COMMIT_SKIP_REASONS = frozenset({"download_failed"})`
(`src/prinfo/exporter.py:429`) is the actionable set; `removed` and
`missing_path` are benign. `src/prinfo/cli.py:195-207` logs a WARNING naming
the actionable count when it is non-zero and an INFO naming the benign count
when it is non-zero, instead of one WARNING for the raw total.

### REQ-3: Check-log summary severity split

`ExportResult` gains `skipped_check_reasons: Mapping[str, int]`, a
per-reason-code breakdown of `skipped_checks`, populated the same way
`skipped_file_reasons` is populated for commit files. The actionable set for
check logs is `{"missing_log_content"}`; `unsupported_check_type` is benign.
The CLI check-log summary branch (currently `src/prinfo/cli.py:167-168`,
`if result.skipped_checks: logger.warning(...)`) is replaced with the same
split the commit-file branch uses: a WARNING naming the actionable count when
non-zero, an INFO naming the benign count when non-zero.

### REQ-4: Per-item check-log log levels mirror commit files

`export_pr_check_logs` currently logs both check-log skip reasons at WARNING
(`src/prinfo/exporter.py:119` for `unsupported_check_type`, `:135` for
`missing_log_content`). The `unsupported_check_type` per-item log moves to
INFO, matching the treatment `removed` already gets in commit-file export
(`src/prinfo/exporter.py:466`, INFO). `missing_path` records its skip without
logging a per-item line at all (`src/prinfo/exporter.py:452-463`). The
`missing_log_content` per-item log stays at WARNING, matching
`download_failed` (`src/prinfo/exporter.py:483`, WARNING). This is a visible
behaviour change: a run against a PR with only external CI checks no longer
emits a WARNING line per check.

### REQ-5: Shared severity helper used by both summary branches

A single helper function, taking the total skipped count, the per-reason-code
breakdown mapping and the actionable reason-code set, decides the actionable
and benign counts and logs the WARNING and INFO lines with mode-specific
wording. Both the commit-file summary branch and the check-log summary branch
in `src/prinfo/cli.py` call this one helper instead of each repeating the
same split inline. The four dataclasses (`ExportResult`, `CommitExportResult`,
`CommentExportResult`, `CommitLogExportResult`) keep their current, separate
shapes; only the summary logging is shared.

### REQ-6: Comment-source behaviour confirmed correct and left unchanged

No code change is made to `export_pr_comments` or to the `skipped_sources`
summary branch in `src/prinfo/cli.py:181-185`. The finding - that all four
comment-source call sites emit only `source_unavailable`, which always means
a failed `gh` call, so every skip is actionable and the existing unconditional
warning is already correct - is recorded in `analysis.md`. A test asserts
that every `reason_code` produced by `export_pr_comments` across all four
source failures is a member of the single-element actionable set
`{"source_unavailable"}`, so the finding cannot silently rot if a future
change adds a second comment-source reason code.

### REQ-7: Documentation updated for check-log skip severity

`README.md` and `skills/prinfo/references/outputs.md` (which already has a
`## How to explain skipped checks` section) are updated to describe the
check-log severity split: the actionable and benign reason codes, the WARNING
versus INFO behaviour of the summary, and the change to per-item logging for
`unsupported_check_type`. Wording matches the style already used for the
commit-file skip-reason sections in both documents.

## Non-Requirements

- No severity split for `skipped_sources`; it stays a single unconditional
  warning, because every comment-source reason code is actionable.
- No new reason codes invented for any mode; the actionable/benign
  classification uses only the reason codes that already exist.
- No top-level aggregate breakdown added to `commits-manifest.json`; the
  per-commit `skipped` array already carries `reason_code`, and REQ-1 is
  already implemented on that basis.
- No protocol or dataclass restructuring of the four result types
  (`ExportResult`, `CommitExportResult`, `CommentExportResult`,
  `CommitLogExportResult`); REQ-5's helper takes plain arguments and is called
  from each branch, not looped over a common interface.
- No change to JSON output key names or ordering in `manifest.json`,
  `commits-manifest.json`, `comments.json` or `commit-log.json`.

## Acceptance Criteria

- **AC-1** - every `commits-manifest.json` commit entry's `skipped` array
  carries `path`, `status`, `additions`, `deletions`, `changes`,
  `previous_path`, `reason_code` and `reason` for each skipped file, with no
  need to open `commits/<sha>/_commit.json` (REQ-1)
- **AC-2** - a commit-file export mixing `download_failed` with `removed`
  and/or `missing_path` skips produces one WARNING naming only the
  `download_failed` count and one INFO naming the combined benign count
  (REQ-2)
- **AC-3** - a check-log export mixing `missing_log_content` with
  `unsupported_check_type` skips produces one WARNING naming only the
  `missing_log_content` count and one INFO naming the `unsupported_check_type`
  count, and `ExportResult.skipped_check_reasons` reports the correct
  per-reason-code breakdown (REQ-3)
- **AC-4** - a check with `unsupported_check_type` logs its per-item skip at
  INFO and a check with `missing_log_content` logs its per-item skip at
  WARNING, verified by capturing log records at each level (REQ-4)
- **AC-5** - the commit-file and check-log summary branches in
  `src/prinfo/cli.py` both call the same shared severity-logging function,
  verified by a test that patches the helper once and asserts it is invoked
  for both a commit-file result and a check-log result (REQ-5)
- **AC-6** - a test drives `export_pr_comments` through all four source
  failures and asserts every `reason_code` recorded in `skipped_sources` is
  `"source_unavailable"`, the single actionable code, and that no code change
  was made to `export_pr_comments` or its CLI summary branch (REQ-6)
- **AC-7** - `README.md` and `skills/prinfo/references/outputs.md` document
  the check-log actionable and benign reason codes, the WARNING/INFO summary
  split, and the per-item log-level change, and `markdownlint-cli2` reports no
  findings on either file (REQ-7)
- **AC-8** - `uv run ruff check src tests` is clean on the finished branch,
  with no suppression directive added (REQ-1, REQ-2, REQ-3, REQ-4, REQ-5,
  REQ-6, REQ-7)
- **AC-9** - `uv run pytest -q` passes on the finished branch, with the test
  count higher than the pre-task baseline and no previously passing test
  removed or weakened (REQ-1, REQ-2, REQ-3, REQ-4, REQ-5, REQ-6, REQ-7)

## Deliverables

| Deliverable | Type |
| ----------- | ---- |
| src/prinfo/exporter.py | Update |
| src/prinfo/cli.py | Update |
| tests/test_exporter.py | Update |
| tests/test_cli.py | Update |
| README.md | Update |
| skills/prinfo/references/outputs.md | Update |
