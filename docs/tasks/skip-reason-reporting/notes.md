# Notes: Spec-to-Code Drift

Recorded at the start of the implementation run, before any code was written.
Every claim below was checked against the working tree and `git log`, not
inferred from the task documents.

## Drifts

### D1: Phase 1 is already committed and merged, not uncommitted

- **Spec reference**: `implementation_plan.md`, "Phase 1: Commit finished
  commit-export work"; `PRD.md`, "Background" ("already implemented, tested and
  verified in the working tree on `fix/commit-skip-reasons-repro`
  (uncommitted)"); `progress.md`, Phase 1, last two unchecked items;
  `open_questions.md`, Q6.
- **Code reference**: `git log --oneline -1` reports `2bedef1 Explain skipped
  commit files and split their severity (#4)` on `main`, whose body says
  `Closes #3`. `git show --stat 2bedef1` includes `src/prinfo/exporter.py`,
  `src/prinfo/cli.py`, `tests/test_exporter.py`, `tests/test_cli.py`,
  `README.md` and `skills/prinfo/references/outputs.md`.
  `src/prinfo/exporter.py:429` already defines
  `ACTIONABLE_COMMIT_SKIP_REASONS`, `:55` already defines
  `CommitExportResult.skipped_file_reasons`, and `src/prinfo/cli.py:195-212`
  already carries the WARNING/INFO split.
- **Difference**: the plan asks Phase 1 to stage and commit six files that are
  already committed and merged through pull request #4; `git status` is clean
  and `git diff --stat main` is empty.

### D2: The task folder is tracked, not untracked

- **Spec reference**: `verification.md`, "Current Skip-Reason Shape"
  ("Expected: shows the six files ... as modified, and
  `docs/tasks/skip-reason-reporting/` as untracked").
- **Code reference**: `git ls-files docs/tasks/skip-reason-reporting/` lists
  all six task documents, and `git log -1 -- docs/tasks/skip-reason-reporting/`
  reports `2bedef1`.
- **Difference**: the documents were committed alongside the Phase 1 code, so
  the "before state" the verification plan describes no longer exists and its
  `git diff --stat main` check reports nothing.

### D3: `missing_path` has no per-item log at all

- **Spec reference**: `PRD.md`, REQ-4 ("matching the treatment `removed` and
  `missing_path` already get in commit-file export
  (`src/prinfo/exporter.py:466`, INFO)").
- **Code reference**: `src/prinfo/exporter.py:452-463` - the `if not file.path`
  branch appends a `missing_path` record and `continue`s with no `LOGGER` call.
  The INFO log at `:466-471` belongs to the `removed` branch only.
- **Difference**: only `removed` logs per item at INFO; `missing_path` is
  silent. REQ-4 describes a treatment `missing_path` does not actually have.
  This does not change the check-log work REQ-4 asks for, but the sentence it
  reasons from is inaccurate.

### D4: The Phase 4 guard test cannot be written the way the plan describes

- **Spec reference**: `implementation_plan.md`, "Test Work - Phase 4" ("drive
  `export_pr_comments` with a fake `GhCli` whose `list_pr_issue_comments`,
  `list_pr_review_comments`, `list_pr_reviews` and `list_pr_review_threads`
  each raise `GhCliError`, and assert every `reason_code` recorded in the
  result's `skipped_sources` equals `"source_unavailable"`"); `PRD.md`, AC-6
  ("a test drives `export_pr_comments` through all four source failures and
  asserts every `reason_code` recorded in `skipped_sources` is
  `"source_unavailable"`").
- **Code reference**: two independent obstacles.
  - `src/prinfo/exporter.py:253-254` - `if len(skipped_sources) == 4: raise
    ExportError(...)`. Failing all four sources in one call raises before any
    result is returned, so there is nothing to assert against. That path is
    already covered by
    `tests/test_exporter.py:1006` (`test_export_pr_comments_raises_when_every_source_fails`).
  - `src/prinfo/exporter.py:98` - `CommentExportResult.skipped_sources: int`.
    The result carries a count, not records. The `reason_code` values exist
    only in the `skipped_sources` array written to `comments.json`.
- **Difference**: "the result's `skipped_sources`" holds no reason codes, and
  driving all four failures in a single call cannot produce a result at all.

### D4 resolution

Fail exactly one source per call, once for each of the four sources, and assert
the single `skipped_sources` entry in the written `comments.json` carries
`reason_code == "source_unavailable"` and the expected `source`. This still
drives every one of the four call sites through its failure path, which is what
AC-6 is actually protecting, and it returns a result each time. It does not
duplicate the existing all-four-fail test, which asserts the `ExportError`.

## Candidate solutions

### 01: Treat Phase 1 as satisfied by history, amend the task documents, implement Phases 2 to 5

- **Approach**: mark Phase 1's remaining `progress.md` items `[x]` with a note
  naming `2bedef1` as the commit that satisfied them; correct the "uncommitted"
  framing in `PRD.md` Background, `implementation_plan.md` Phase 1 and
  `verification.md` Pre-Implementation Verification so they describe the merged
  commit; correct REQ-4's `missing_path` sentence; leave every requirement,
  acceptance criterion and later phase untouched; implement Phases 2 to 5 as
  written.
- **Scope**: four task documents edited for accuracy, no requirement changed;
  `src/prinfo/exporter.py`, `src/prinfo/cli.py`, `tests/test_exporter.py`,
  `tests/test_cli.py`, `README.md`,
  `skills/prinfo/references/outputs.md` changed by Phases 2 to 5 exactly as
  planned.
- **Pros**: the drift is documentation-only, so amending the documents is the
  cheaper and more honest fix; no code is written twice; the acceptance
  criteria AC-1 and AC-2 stay ticked on the evidence that actually exists
  (the merged commit and its four tests); the remaining phases are unaffected.
- **Cons**: the task folder ends up describing a Phase 1 that this run did not
  perform, which a reader must take on the strength of the recorded commit SHA.
- **Risk**: low. Nothing executable depends on the corrected sentences.

### 02: Re-do Phase 1 by reverting `2bedef1` and re-committing it on this branch

- **Approach**: revert the merged commit and reapply it from this branch so the
  run literally performs Phase 1 as the plan describes.
- **Scope**: two extra commits on `main`'s history, and a pull request whose
  diff re-adds code that is already on `main`.
- **Pros**: the plan is followed to the letter.
- **Cons**: it rewrites shipped, reviewed history to satisfy a sentence in a
  planning document; the pull request would show a revert and a re-apply of
  work already reviewed in #4; it risks losing the commit-export fix if the
  revert half merges and the re-apply half does not.
- **Risk**: high, and the benefit is purely cosmetic.

### 03: Leave every task document as written and implement Phases 2 to 5 silently

- **Approach**: change no task document; implement the remaining phases and
  leave Phase 1's two items unchecked forever.
- **Scope**: code and test files only.
- **Pros**: smallest diff.
- **Cons**: `progress.md` would end the run with unchecked items that will
  never be checked, which reads as incomplete work rather than as work done
  elsewhere; `PRD.md` and `verification.md` would keep stating that the
  commit-export fix is uncommitted, which is false and would mislead the next
  reader and any future re-run of this task.
- **Risk**: medium. The falsehood is durable and sits in the record a reviewer
  reads first.

### 04: Amend the spec to drop Phase 1 entirely

- **Approach**: delete Phase 1 from `implementation_plan.md` and `progress.md`,
  and delete REQ-1, REQ-2, AC-1 and AC-2 from `PRD.md`, so the task covers only
  the sibling-mode work.
- **Scope**: heavy edits to `PRD.md`, `implementation_plan.md`,
  `progress.md` and `verification.md`.
- **Pros**: the task folder would describe only work this run performs.
- **Cons**: it discards the answer to Q1, where the user explicitly chose
  option (b) - "the task re-documents all three parts, restating the finished
  commit-export work as completed phases so the folder mirrors the whole
  issue." Deleting REQ-1, REQ-2, AC-1 and AC-2 reverses a decision the user
  made, and loses the traceability from issue #3 to the commit that closed it.
- **Risk**: medium-high. It contradicts a recorded user decision.

## Chosen option

**01**. See `solution_01.md`.
