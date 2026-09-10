# Analysis 1 - Catch GitHub errors inside each export mode

## Decision: Valid - fix applied

The per-mode loop in `main` recorded only `ExportError`, while every exporter entry point can also raise `GhCliError` from `gh.ensure_available()`, `gh.detect_repo()`, `gh.list_pr_checks()`, `gh.list_pr_commits()` and `gh.get_commit_details()`; those escaped to the outer `except` and aborted the whole run, so one failing mode suppressed the other requested modes. The loop now records `GhCliError` alongside `ExportError`, `_ModeRun.error` accepts either type, and the "no mode produced a result" path re-raises whichever error came first so the exit code and the logged message are unchanged for a single-mode run.

**Why:** PRD REQ-6 states that in `main` each mode records its own error, a failure in one does not prevent the others from running, and the run exits non-zero only when no mode produced a result. `GhCliError` is a sibling of `ExportError` (both plain `RuntimeError` subclasses, `src/prinfo/gh.py:37` and `src/prinfo/exporter.py:29`) and is the error type the `gh` client raises for API and permission failures, so leaving it out of the per-mode handler made the contract hold only for validation failures. Catching it at the loop was chosen over normalizing inside each exporter because the exporters already use `GhCliError` deliberately for per-item isolation, and re-wrapping there would have changed four call sites and the messages they log.

**Commit:** 664a748 - fix(cli): address review feedback for PR #2
