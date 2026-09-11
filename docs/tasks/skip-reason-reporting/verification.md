# Verification Plan: Skip Reason Severity Reporting

## Purpose

Proves that `commits-manifest.json` and the check-log summary carry the
actionable/benign distinction the same way, that no code change was made
where none was warranted (comment sources), and that the finished
commit-export work is committed as its own commit before the remaining
phases build on top. Every command below is the project's real gate, taken
from the Development section of `README.md` and the toolchain named in this
task.

## Pre-Implementation Verification

### Existing Tests Pass

```bash
uv run pytest -q
```

Expected: all pass, 76 tests, since the commit-export fix (REQ-1, REQ-2) is
already implemented and merged as commit `2bedef1`. Record the count so the
post-implementation run can be compared against it.

### Linter Baseline

```bash
uv run ruff check src tests
```

Expected: clean.

### Type Check Baseline

```bash
npx pyright src/prinfo/exporter.py src/prinfo/cli.py
```

Expected: 0 errors. Not a project gate, but the baseline this task must not
regress.

### Markdown Baseline

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean.

### Current Skip-Reason Shape

```bash
git show --stat 2bedef1
```

Expected: lists the six files of the commit-export fix, plus the six task
documents, all committed together in `2bedef1`. The working tree is clean and
`git diff --stat main` is empty, because Phase 1 is already merged. This is
the before state for Phase 2.

## Post-Implementation Verification

### Per-Phase Verification

#### Phase 1: Commit finished commit-export work

Covers REQ-1, REQ-2.

```bash
uv run pytest -q
uv run ruff check src tests
npx pyright src/prinfo/exporter.py src/prinfo/cli.py
npx markdownlint-cli2 "**/*.md" "#node_modules"
git show --stat 2bedef1
```

Expected: all four checks clean, and `2bedef1` contains the six files, with
its body closing the two numbered defects in issue #3.

#### Phase 2: Shared severity helper

Covers REQ-5.

```bash
uv run pytest tests/test_cli.py -q
uv run ruff check src tests
```

Expected: the four pre-existing commit-file severity tests pass with no
change to their assertions, proving the extraction changed no behaviour; the
new `_log_skip_severity` unit tests pass for the mixed, actionable-only,
benign-only and zero-total cases.

#### Phase 3: Check-log severity split

Covers REQ-3, REQ-4.

```bash
uv run pytest tests/test_exporter.py tests/test_cli.py -q
uv run ruff check src tests
npx pyright src/prinfo/exporter.py src/prinfo/cli.py
```

Expected: `ExportResult.skipped_check_reasons` reports the correct breakdown
for a mixed batch; a check-log export with only `unsupported_check_type`
skips logs at INFO per item and produces no WARNING in the summary; a
check-log export with `missing_log_content` skips logs at WARNING per item
and the summary WARNING names only that count.

#### Phase 4: Comment-source finding and guard test

Covers REQ-6.

```bash
uv run pytest tests/test_exporter.py -k comments -q
git diff src/prinfo/exporter.py src/prinfo/cli.py
```

Expected: the guard test passes for each of the four sources in turn,
asserting the `reason_code` `export_pr_comments` writes to `comments.json` is
`"source_unavailable"`; the `git diff` against the end of Phase 3 is empty
for both files, confirming REQ-6 added no production code.

#### Phase 5: Documentation

Covers REQ-7.

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean across `README.md`, `skills/prinfo/references/outputs.md`
and the five task files. Every reason code and log level named in the docs
is manually cross-checked against `src/prinfo/exporter.py`.

### Linter

```bash
uv run ruff check src tests
```

Expected: clean, with no findings introduced by this task and no suppression
directive added to source.

### Type Check

```bash
npx pyright src/prinfo/exporter.py src/prinfo/cli.py
```

Expected: 0 errors, matching the pre-task baseline.

### Markdown Linter

```bash
npx markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean across `README.md`, `skills/prinfo/references/outputs.md`
and the five task files.

### Regression Check

```bash
uv run pytest -q
```

Expected: all pass, with a test count higher than the pre-implementation
baseline and no previously passing test removed or weakened.

### Manual Severity Check

Run a check-log export against a PR whose checks include at least one
external (non-Actions) status check, using `--log-level DEBUG`:

```bash
uv run prinfo --repo owner/repo --pr <n> --skip-empty-logs --log-level DEBUG --output-dir <scratch>/pr-<n>
```

Expected: each external status check logs at INFO, not WARNING; the summary
line shows no WARNING when every skip is `unsupported_check_type`; a check
whose log content is genuinely missing still logs at WARNING both per item
and in the summary.

## Final Acceptance Verification

The feature can be accepted when all items are true:

- [x] AC-1 - every `commits-manifest.json` commit entry's `skipped` array
      carries `path`, `status`, `additions`, `deletions`, `changes`,
      `previous_path`, `reason_code` and `reason`, with no need to open
      `commits/<sha>/_commit.json` - verified by: Phase 1 verification,
      `uv run pytest -q`
- [x] AC-2 - a commit-file export mixing `download_failed` with `removed`
      and/or `missing_path` skips produces one WARNING naming only the
      `download_failed` count and one INFO naming the combined benign count
      - verified by: Phase 1 verification, the four pre-existing commit-file
      severity tests
- [ ] AC-3 - a check-log export mixing `missing_log_content` with
      `unsupported_check_type` skips produces one WARNING naming only the
      `missing_log_content` count and one INFO naming the
      `unsupported_check_type` count, and `ExportResult.skipped_check_reasons`
      reports the correct per-reason-code breakdown - verified by: Phase 3
      verification
- [ ] AC-4 - a check with `unsupported_check_type` logs its per-item skip at
      INFO and a check with `missing_log_content` logs its per-item skip at
      WARNING - verified by: Phase 3 verification, the `caplog` tests
- [ ] AC-5 - the commit-file and check-log summary branches in
      `src/prinfo/cli.py` both call the same shared severity-logging
      function - verified by: Phase 2 and Phase 3 verification
- [ ] AC-6 - a test drives `export_pr_comments` through each of the four
      source failures, one per run, and asserts every `reason_code` recorded
      in the `skipped_sources` array of `comments.json` is
      `"source_unavailable"`, the single actionable code, with no production
      code change made - verified by: Phase 4 verification
- [ ] AC-7 - `README.md` and `skills/prinfo/references/outputs.md` document
      the check-log actionable and benign reason codes, the WARNING/INFO
      summary split, and the per-item log-level change, and
      `markdownlint-cli2` reports no findings on either file - verified by:
      Phase 5 verification
- [ ] AC-8 - `uv run ruff check src tests` is clean on the finished branch,
      with no suppression directive added - verified by: Linter section
- [ ] AC-9 - `uv run pytest -q` passes on the finished branch, with the test
      count higher than the pre-task baseline and no previously passing test
      removed or weakened - verified by: Regression Check section
