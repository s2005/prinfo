# Solution 01: Amend the Phase 1 framing, implement Phases 2 to 5 as planned

## Chosen approach

Phase 1's work exists and is merged. `2bedef1` ("Explain skipped commit files
and split their severity (#4)", body `Closes #3`) carries every deliverable the
plan lists for Phase 1: the embedded `skipped` array in
`commits-manifest.json` records, `CommitExportResult.skipped_file_reasons`,
`ACTIONABLE_COMMIT_SKIP_REASONS`, the WARNING/INFO split in
`src/prinfo/cli.py`, the four supporting tests and both document updates.

So Phase 1 is closed by recording the commit that satisfied it, not by
performing it again. The task documents are corrected where they assert the
work is uncommitted, and nothing else about the task changes. Phases 2 to 5
are implemented exactly as `implementation_plan.md` specifies.

## Why this beats each rejected option

- **Over 02 (revert and re-apply)**: 02 rewrites reviewed, merged history so
  that a planning sentence becomes literally true. The gain is cosmetic and the
  cost is a pull request that reverts and re-adds shipped code, with a real
  window in which the commit-export fix is absent from `main`. The drift is in
  the documents, so the documents are what should change.
- **Over 03 (change nothing, implement silently)**: 03 leaves `PRD.md` and
  `verification.md` asserting that the commit-export fix is uncommitted, and
  leaves two `progress.md` items permanently unchecked. The record would then
  say the task is incomplete when it is not, and would mislead anyone re-running
  it. Correcting four sentences costs almost nothing and removes a durable
  falsehood.
- **Over 04 (delete Phase 1 and REQ-1/REQ-2)**: 04 reverses the user's recorded
  answer to Q1, which chose option (b) - keep all three parts of issue #3 in
  this folder, with the finished commit-export work restated as completed
  phases. It would also break the traceability table and delete AC-1 and AC-2,
  which are genuinely satisfied and genuinely verifiable.

## Drifts resolved

| Drift | Resolution |
| ----- | ---------- |
| D1 | `progress.md` Phase 1 items ticked, each naming `2bedef1`; the "uncommitted" wording corrected in `PRD.md` Background, `implementation_plan.md` Phase 1 and `verification.md` Pre-Implementation Verification |
| D2 | `verification.md` "Current Skip-Reason Shape" rewritten to describe the merged state it now finds |
| D3 | REQ-4's sentence corrected: only `removed` logs per item at INFO; `missing_path` records its skip without logging |

## Files to change

| File | Phase | Change |
| ---- | ----- | ------ |
| docs/tasks/skip-reason-reporting/PRD.md | 1 | Correct the Background and REQ-4 wording |
| docs/tasks/skip-reason-reporting/implementation_plan.md | 1 | Correct Phase 1 to describe the merged commit |
| docs/tasks/skip-reason-reporting/verification.md | 1 | Correct the pre-implementation baseline |
| docs/tasks/skip-reason-reporting/progress.md | all | Tick items as each phase completes |
| src/prinfo/cli.py | 2, 3 | Add `_log_skip_severity`; route both summary branches through it |
| src/prinfo/exporter.py | 3 | `ACTIONABLE_CHECK_SKIP_REASONS`, `skipped_check_reasons`, per-item log level |
| tests/test_cli.py | 2, 3 | Helper unit tests; check-log summary split tests |
| tests/test_exporter.py | 3, 4 | Breakdown and `caplog` tests; comment-source guard test |
| README.md | 5 | Document the check-log severity split |
| skills/prinfo/references/outputs.md | 5 | Extend "How to explain skipped checks" |

## Implementation outline

1. **Phase 1 (documents only)** - correct the four sentences named above and
   tick Phase 1 in `progress.md`, each item naming `2bedef1` as its evidence.
   No source change; AC-1 and AC-2 stay ticked on that commit and its tests.
2. **Phase 2** - add `_log_skip_severity(logger, *, total, breakdown,
   actionable_reasons, actionable_message, benign_message)` to
   `src/prinfo/cli.py` and make the `CommitExportResult` branch its only
   caller. Pure refactor; the four existing commit-file tests must pass with no
   edits to their assertions. Add four direct unit tests for the helper.
3. **Phase 3** - add `ACTIONABLE_CHECK_SKIP_REASONS = frozenset({"missing_log_content"})`
   and `ExportResult.skipped_check_reasons`, populate the breakdown with
   `Counter` in `export_pr_check_logs`, move the `unsupported_check_type`
   per-item log from WARNING to INFO, and route the `ExportResult` summary
   branch through `_log_skip_severity`.
4. **Phase 4** - add the comment-source guard test only. No production change.
5. **Phase 5** - document the check-log split in `README.md` and
   `skills/prinfo/references/outputs.md`.

## Verification steps

- Phase 2: `uv run pytest tests/test_cli.py`, `uv run ruff check src tests`.
- Phase 3: `uv run pytest tests/test_exporter.py tests/test_cli.py`,
  `uv run ruff check src tests`, `npx pyright src/prinfo/exporter.py src/prinfo/cli.py`.
- Phase 4: `uv run pytest tests/test_exporter.py -k comments`, plus a
  `git diff` over the two source files showing no change since Phase 3.
- Phase 5: `npx markdownlint-cli2 "**/*.md" "#node_modules"`, plus a manual
  cross-check of every reason code and log level named in the documents against
  `src/prinfo/exporter.py`.
- Final: `uv run pytest -q` above the 76-test baseline, and
  `uv run ruff check src tests` clean with no suppression directive added.
