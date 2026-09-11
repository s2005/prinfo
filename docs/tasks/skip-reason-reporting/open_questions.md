# Open Questions: Cover Every Defect Described in Issue #3

## Q1: Does this task cover the sibling modes, given the commit-export half is already implemented?

- **Why it matters**: Decides whether this task has any implementation phases at all. Issue #3 numbers two defects, both about `--export-commit-files`, and both are already fixed in the working tree on `fix/commit-skip-reasons-repro` (uncommitted). The issue then closes with "Same pattern in `skipped_checks` (`src/prinfo/cli.py:167`) and `skipped_sources` (`:180`). Worth fixing once rather than three times." That sentence is the only part of the issue not yet covered. It was deliberately excluded from the current diff on one-ticket-one-fix grounds and recorded as needing its own decision.
- **Options**: (a) this task covers only the closing sentence - the sibling modes - and treats the two numbered defects as done; (b) this task re-documents all three parts, restating the finished commit-export work as completed phases; (c) this task is abandoned and the sibling modes get their own issue instead.
- **Recommended**: (a) - the two numbered defects are implemented, tested and verified, so re-planning them produces documentation that describes work already finished. The task should carry the one part of the issue that has no coverage, and record the finished half as background.
- **Answer**: (b) - the task re-documents all three parts, restating the finished commit-export work as completed phases so the folder mirrors the whole issue. Decided by user.

## Q2: Is `missing_log_content` a benign check skip or an actionable one?

- **Why it matters**: Decides the contents of the actionable-reason set for check logs, and therefore whether a run that skips expired logs warns or not. Check-log export produces exactly two reason codes (`src/prinfo/exporter.py:124` and `:144`). `unsupported_check_type` means the check is not a GitHub Actions job at all - an external CI status - which is normal and unfixable by the user. `missing_log_content` means `gh` reported no downloadable log content for a real Actions job, which happens both when GitHub has aged the log out (benign, common on old PRs) and when something is genuinely wrong.
- **Options**: (a) actionable set is `{}` for check logs - both codes benign, so the summary never warns; (b) actionable set is `{"missing_log_content"}` - only the non-Actions checks are treated as normal; (c) keep a single severity for check logs and change nothing.
- **Recommended**: (b) - it matches the commit-file split, where "the artifact cannot exist" is benign and "the fetch did not produce what it should have" is actionable. It also preserves a warning for the case a user can act on, such as re-running a workflow to regenerate logs.
- **Answer**: (b) - the actionable set for check logs is `{"missing_log_content"}`; `unsupported_check_type` is benign. Decided by user.

## Q3: Does `skipped_sources` need any change at all?

- **Why it matters**: The issue names `skipped_sources` alongside `skipped_checks` as sharing the warn-on-anything pattern, so a reader would expect this task to change it. Reading the code contradicts that. Comment-source export emits exactly one reason code, `source_unavailable`, at all four call sites (`src/prinfo/exporter.py:223`, `:232`, `:241`, `:250`), and it always means a `gh` call failed. Every skip is actionable, so the existing unconditional warning is already correct and a severity split would have nothing to separate.
- **Options**: (a) make no code change for comment sources, and record in the task why the issue's expectation does not hold; (b) add the breakdown field to `CommentExportResult` anyway for symmetry, even though every count maps to one actionable code; (c) split anyway by inventing new reason codes that distinguish kinds of `gh` failure.
- **Recommended**: (a) - a severity split over a single actionable code is dead code, and (c) invents a classification no defect asks for. The issue's closing sentence is accurate about `skipped_checks` and inaccurate about `skipped_sources`; the task should say so and close that part of the issue with a finding rather than a change.
- **Answer**: (a) - no code change for comment sources. Settled by reading `src/prinfo/exporter.py:223`, `:232`, `:241` and `:250`, which show one reason code, `source_unavailable`, at every call site, always meaning a failed `gh` call.

## Q4: Should the per-item log level for benign check skips change too?

- **Why it matters**: Decides whether this task touches `export_pr_check_logs` itself or only the CLI summary. Commit-file export already logs benign skips per item at INFO (`src/prinfo/exporter.py:466`) and real failures at WARNING (`:487`), which is what let the summary split cleanly. Check-log export logs both of its reason codes per item at WARNING (`:118` and `:134`). Leaving that alone means a run with only external CI checks still emits one WARNING line per check even after the summary stops warning, which undercuts the fix from the user's point of view.
- **Options**: (a) change the per-item level for `unsupported_check_type` to INFO and leave `missing_log_content` at WARNING, mirroring commit files; (b) change only the summary line and leave both per-item logs at WARNING; (c) change both per-item logs to INFO.
- **Recommended**: (a) - it makes check-log output consistent with commit-file output and removes the noise the fix is meant to remove. It is a visible behaviour change to per-check logging and needs to be called out as such.
- **Answer**: (a) - `unsupported_check_type` moves to INFO, `missing_log_content` stays at WARNING, mirroring commit files. Decided by user.

## Q5: One shared severity helper, or per-mode logic?

- **Why it matters**: Decides the shape of the diff and how much of `cli.py` moves. The issue says "Worth fixing once rather than three times", which reads as a request for one mechanism. The commit-file fix currently uses a mode-specific constant, `ACTIONABLE_COMMIT_SKIP_REASONS`, read inline in the `CommitExportResult` branch of `_log_mode_summaries`.
- **Options**: (a) add a second mode-specific constant for check logs and repeat the small inline split; (b) extract a shared helper taking a count, a breakdown mapping and an actionable set, and call it from both branches; (c) restructure the result dataclasses behind a common protocol so the summary block loops instead of branching.
- **Recommended**: (b) - with two real call sites the duplication is worth removing, and a helper keeps the wording of the two messages in one place. (c) is a larger refactor of four result types that no defect in the issue requires.
- **Answer**: (b) - a shared helper takes the total, the breakdown mapping and the actionable set, and is called from both the commit-file and check-log summary branches. Settled by recommendation against the two real call sites this task creates.

## Q6: Does this task also own committing the existing uncommitted work?

- **Why it matters**: Decides where the task starts and what a reviewer sees. The commit-export fix, its two regression tests, two new positive-path tests, the `_CommitFolderResult` typing change and the documentation updates are all sitting uncommitted in the working tree.
- **Options**: (a) the existing work is committed first as its own commit closing the numbered defects, and this task builds on top; (b) this task's phases and the existing work land together as one commit; (c) this task is planned now and committed later in whatever order suits the PR.
- **Recommended**: (a) - the two halves are separable and were argued separately, so they should be reviewable separately. It also means a revert of the sibling-mode change does not take the commit-export fix with it.
- **Answer**: (a) - the finished commit-export work is committed first as its own commit, and this task's remaining phases build on top. Decided by user.

## Resolution Summary

| ID | Status | Carried by |
| -- | ------ | ---------- |
| Q1 | Answered | Whole plan - Phases 1 to 5 |
| Q2 | Answered | REQ-3 |
| Q3 | Answered | REQ-6, Non-Requirements |
| Q4 | Answered | REQ-4 |
| Q5 | Answered | REQ-5 |
| Q6 | Answered | Phase 1 |
