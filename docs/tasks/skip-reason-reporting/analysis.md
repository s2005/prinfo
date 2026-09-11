# Analysis: Skip Reason Severity Reporting

## Goal

Carry the check-log warn-on-anything pattern that issue #3 already fixed for
commit files (REQ-1, REQ-2, already implemented) over to check logs (REQ-3,
REQ-4), behind one shared severity helper (REQ-5), and settle whether
comment-source skips need the same treatment (REQ-6), then document the
result (REQ-7).

## Current Behavior

### Skip reason codes, by mode

| Mode | Reason code | Source line | Benign or actionable |
| ---- | ----------- | ----------- | --------------------- |
| Check logs | `unsupported_check_type` | `src/prinfo/exporter.py:124` (per-item WARNING at `:119`) | benign - the check is not a GitHub Actions job at all |
| Check logs | `missing_log_content` | `src/prinfo/exporter.py:144` (per-item WARNING at `:135`) | actionable - a real Actions job returned no downloadable log |
| Comment sources | `source_unavailable` | `src/prinfo/exporter.py:223`, `:232`, `:241`, `:250` | actionable - always a failed `gh` call |
| Commit files | `missing_path` / `removed` / `download_failed` | `:460` / `:475` / `:493` | benign / benign / actionable |

### Commit files (REQ-1, REQ-2 - already implemented)

`_export_commit_folder` (`src/prinfo/exporter.py`) returns a frozen
`_CommitFolderResult` instead of the `dict[str, object]` it used before this
branch started; that typing change took `pyright` on
`src/prinfo/exporter.py` and `src/prinfo/cli.py` from 4 errors to 0. Its
`record` field embeds the full `skipped` list into each commit's entry in
`commits-manifest.json`, matching the pattern already used by `manifest.json`
(top-level `skipped`) and `comments.json` (`skipped_sources`) before this
branch touched either file.

`CommitExportResult` carries `skipped_file_reasons: Mapping[str, int]`, and
`ACTIONABLE_COMMIT_SKIP_REASONS = frozenset({"download_failed"})`
(`src/prinfo/exporter.py:429`) is read inline in the `CommitExportResult`
branch of `_log_mode_summaries` (`src/prinfo/cli.py:195-207`):

```python
if result.skipped_files:
    actionable = sum(
        count
        for reason_code, count in result.skipped_file_reasons.items()
        if reason_code in ACTIONABLE_COMMIT_SKIP_REASONS
    )
    benign = result.skipped_files - actionable
    if actionable:
        logger.warning("%s commit file(s) could not be downloaded.", actionable)
    if benign:
        logger.info(
            "%s commit file(s) cannot be exported (removed in the commit, "
            "or absent from the commit payload).",
            benign,
        )
```

Four tests cover it: two regression tests pinning the pre-fix defects as
resolved, and two positive-path tests for the actionable and benign branches.
The suite is 76 tests passing, `ruff check src tests` clean, `pyright
src/prinfo/exporter.py src/prinfo/cli.py` clean, `markdownlint-cli2` clean.
This work is uncommitted on `fix/commit-skip-reasons-repro`.

### Check logs (REQ-3, REQ-4 - not yet implemented)

`export_pr_check_logs` (`src/prinfo/exporter.py:103`) loops over checks and
appends to `skipped` on two branches:

```python
if check.job_id is None:
    LOGGER.warning("Skipping check without downloadable job log: %s", check.name)
    skipped.append(_skipped_record(check=check, reason=..., reason_code="unsupported_check_type"))
    continue
...
except GhCliError as exc:
    if not _is_missing_log_error(exc):
        raise
    LOGGER.warning("Skipping check '%s' (job %s) because no downloadable log content is available.", ...)
    skipped.append(_skipped_record(check=check, reason=str(exc), reason_code="missing_log_content"))
    continue
```

Both branches log at WARNING per item, and `ExportResult` carries only
`skipped_checks: int`, no breakdown. `src/prinfo/cli.py:167-168` warns on any
non-zero count:

```python
if result.skipped_checks:
    logger.warning("Skipped %s check(s).", result.skipped_checks)
```

This is exactly the pre-fix commit-file shape: one undifferentiated WARNING
at both the summary level and the per-item level, even though
`unsupported_check_type` is normal (an external CI status is not a GitHub
Actions job and was never going to have a log) and `missing_log_content`
signals something a user can investigate, such as re-running a workflow to
regenerate an expired log.

### Comment sources (REQ-6 - confirmed correct, no change)

`export_pr_comments` (`src/prinfo/exporter.py:212`) calls four client
methods (`list_pr_issue_comments`, `list_pr_review_comments`,
`list_pr_reviews`, `list_pr_review_threads`), each in its own `try`, and on
`GhCliError` appends a `_skipped_source_record(source=..., reason=str(exc),
reason_code="source_unavailable")`. All four call sites use the same literal
string `"source_unavailable"`; grep confirms it is the only reason code
`export_pr_comments` ever produces. The CLI summary
(`src/prinfo/cli.py:181-185`) warns unconditionally on any non-zero
`skipped_sources` count:

```python
if result.skipped_sources:
    logger.warning("Skipped %s comment source(s).", result.skipped_sources)
```

Key finding: issue #3's closing sentence claims that `skipped_sources`
shares the pattern with `skipped_checks` and is worth fixing once rather
than three times. Reading the four call sites shows this is factually wrong
for comment sources. There is only one reason code, and it always means a
`gh` call failed - there is no benign branch to route to INFO. A severity
split needs two things to separate: an actionable code and a benign code.
Comment sources have only the former, so the existing unconditional warning
is already the correct behaviour, and a split would produce a permanent
`benign = 0` branch that never fires. The issue is right about
`skipped_checks` and wrong about `skipped_sources`.

The same reading resolves REQ-1's applicability to the two siblings: REQ-1
(embedding the skip list in the manifest) does not apply to either sibling,
because `manifest.json` already embeds its full `skipped` list and
`comments.json` already embeds `skipped_sources` as a list of records, not a
bare count. The only genuinely uncovered work in the entire issue is the
check-log severity split (REQ-3, REQ-4) plus the shared-mechanism request
(REQ-5) and the documentation that follows from it (REQ-7).

### CLI orchestration

`_log_mode_summaries` (`src/prinfo/cli.py:151-217`) branches on the result
type (`ExportResult`, `CommentExportResult`, `CommitExportResult`,
`CommitLogExportResult`) and logs a per-mode summary. It is the single call
site for all four summary blocks, so the shared helper REQ-5 asks for has one
place to be introduced and two places to be called from once REQ-3 lands.

### Tests

`tests/test_exporter.py` and `tests/test_cli.py` already carry the commit-file
severity-split tests (REQ-2) as a template: a fake `GhCli` returning a mix of
`removed`, `missing_path` and `download_failed` skips, asserting
`skipped_file_reasons` and the two log lines via `caplog`. The check-log tests
in Phase 3 copy this shape directly.

## Feasibility

Straightforward. REQ-3 and REQ-4 are a direct port of the commit-file pattern
onto `export_pr_check_logs` and `ExportResult`: add a breakdown mapping, add
an actionable-set constant, change one per-item log level, and route the
summary through the new shared helper. REQ-5 is a small extraction with an
existing single call site to refactor (commit files) and a second call site
about to be created (check logs), so there is no risk of guessing at a shape
the second call site will not fit - both call sites land in the same task.
REQ-6 requires no production code change at all; it is a test that pins the
finding so a future comment-source reason code cannot silently defeat it.
REQ-7 is a doc update following the existing "How to explain skipped checks"
and "How to explain a skipped commit file" sections in
`skills/prinfo/references/outputs.md` as templates.

## Approach

### Recommended: shared helper first, then the check-log split, then the comment-source guard test

Sequence matters here because REQ-5's helper needs a second real call site to
be validated against, not just refactored in isolation. Phase 2 extracts the
helper using the commit-file branch as the only caller, a pure refactor with
no behaviour change, provable by the existing four commit-file tests still
passing unchanged. Phase 3 then adds the check-log breakdown and calls the
same helper from the check-log branch, which is where the helper generality
actually gets exercised. Phase 4 adds the comment-source guard test with no
production change. Phase 5 documents the result.

| Advantages | Disadvantages |
| ---------- | ------------- |
| The helper shape is validated against two real call sites within this task, not guessed at from one | Phase 2 temporarily has only one caller, so a reviewer sees the refactor and the second use land in different commits (Phase 1 vs Phase 3) |
| Each phase diff is reviewable on its own: refactor, then behaviour change, then a pinned finding, then docs | -- |
| Matches Q5, extract a helper called from both the commit-file and check-log summary branches without restructuring the four result dataclasses | -- |

### Alternative: add the check-log split first with its own inline logic, extract the helper afterward

| Advantages | Disadvantages |
| ---------- | ------------- |
| No transitional single-caller state for the helper | Produces a throwaway inline duplicate of the commit-file split that the very next phase deletes, which is more diff for a reviewer to read for no benefit |

Rejected: Q5 already settled the shape, a shared helper rather than per-mode
constants, so writing the duplicate first and removing it next phase adds
churn without adding confidence.

### Alternative: split `skipped_sources` too, for symmetry with the other two modes

Considered and closed by Q3. Rejected because there is nothing to split - one
reason code, always actionable - and doing it anyway would either be dead
code, a benign branch that never fires, or would require inventing a
reason-code taxonomy no defect in issue #3 asks for, which the
one-ticket-one-fix rule forecloses.

## Implementation Notes

- Actionable-set constant naming. `ACTIONABLE_COMMIT_SKIP_REASONS` already
  exists for commit files. The check-log constant is named
  `ACTIONABLE_CHECK_SKIP_REASONS = frozenset({"missing_log_content"})`,
  following the same naming pattern, defined beside its commit-file sibling
  in `src/prinfo/exporter.py`.
- Breakdown population. `skipped_file_reasons` is built with
  `collections.Counter` over the `reason_code` of each skipped-file record.
  `skipped_check_reasons` is built the same way, over the `reason_code` of
  each `_skipped_record` appended in `export_pr_check_logs`.
- Helper signature. `_log_skip_severity(logger, total, breakdown,
  actionable_reasons, actionable_message, benign_message)` computes
  `actionable = sum(count for code, count in breakdown.items() if code in
  actionable_reasons)` and `benign = total - actionable`, then logs
  `logger.warning(actionable_message, actionable)` when `actionable` is
  non-zero and `logger.info(benign_message, benign)` when `benign` is
  non-zero. Both call sites pass their own message strings, so the wording
  each mode already uses is preserved verbatim rather than generalised into
  one generic sentence.
- Per-item log level (REQ-4). Only the `unsupported_check_type` branch
  `LOGGER.warning` at `src/prinfo/exporter.py:119` changes to
  `LOGGER.info`. The `missing_log_content` branch `LOGGER.warning` at `:135`
  is unchanged. This mirrors `removed`/`missing_path` at INFO versus
  `download_failed` at WARNING in commit-file export exactly.
- Guard test shape (REQ-6). The test drives `export_pr_comments` with a
  fake `GhCli` whose four methods all raise `GhCliError`, then asserts every
  `reason_code` recorded in `skipped_sources` is `source_unavailable`, which
  fails the moment a second comment-source reason code is introduced without
  a corresponding update to this task finding.
- No emoji or Unicode in code, matching the rest of the codebase; this
  applies to the new log-message strings.
- Encoding. No new file writes are introduced by this task; REQ-1 and
  REQ-2 already write `commits-manifest.json` with `encoding="utf-8"`, and no
  requirement here adds another write path.

## Risks

| Risk | Mitigation |
| ---- | ---------- |
| The shared helper message strings drift from the mode-specific wording already shipped for commit files | The helper takes the message strings as parameters rather than building them, so the existing commit-file wording is passed through unchanged and pinned by the existing four tests |
| Changing `unsupported_check_type` to INFO silently changes what a caller log-level filter shows, breaking a downstream consumer that greps for WARNING | This is REQ-4 explicit, called-out behaviour change; `README.md` and `skills/prinfo/references/outputs.md` document it under REQ-7 so it is discoverable rather than a silent diff |
| A future comment-source call site adds a second reason code and nobody notices the severity-split finding no longer holds | REQ-6 guard test fails the moment that happens, turning a silent doc-vs-code drift into a build failure |
| Extracting the shared helper before the check-log call site exists risks guessing a shape the second caller does not fit | Sequencing, Phase 2 helper then Phase 3 second caller, keeps both call sites inside this task, so the shape is validated, not assumed |

## Test Strategy

| Level | File | What it covers |
| ----- | ---- | --------------- |
| Unit - exporter | `tests/test_exporter.py` | `ExportResult.skipped_check_reasons` breakdown for a mixed batch (AC-3); per-item log level for each check-log reason code via `caplog` (AC-4); `export_pr_comments` reason-code guard across all four failing sources (AC-6) |
| Unit - CLI | `tests/test_cli.py` | Check-log summary WARNING/INFO split for a mixed batch (AC-3); shared helper invoked from both the commit-file and check-log branches (AC-5); existing commit-file severity tests still pass unchanged (AC-2 regression) |
| Gate | -- | `uv run ruff check src tests`, `uv run pytest -q` (AC-8, AC-9); `npx markdownlint-cli2 "**/*.md" "#node_modules"` (AC-7) |

No new integration or live-`gh` test is added: every test in the suite runs
against injected fakes, and this task changes only log levels and a count
breakdown, none of which needs a live repository to verify.
