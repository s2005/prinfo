# Open Questions: Export PR Comments and Commit Log

## Q1: What output format should `--export-comments` write?

- **Why it matters**: Decides whether Phase 2 writes one serializer or two, and whether the export is machine-readable, human-readable, or both. The existing exports are JSON manifests only (`manifest.json`, `commits-manifest.json`), so a Markdown transcript would be a new output shape for this tool.
- **Options**: (a) `comments.json` only, matching the existing manifest convention; (b) `comments.json` plus a rendered `comments.md` transcript ordered by time; (c) `comments.md` only.
- **Recommended**: (b) - the JSON keeps parity with the other exports and stays diffable, while the Markdown transcript is what makes a review readable when the export is handed to a person or an agent. The renderer is small and reads only from the same in-memory records.
- **Answer**: (b) - decided by user.

## Q2: Which comment sources should be exported?

- **Why it matters**: GitHub splits PR discussion across three REST endpoints. Picking fewer means a silently incomplete export; picking all three means three calls per run and a merge step. Resolved/unresolved state of a review thread is a fourth concern and exists only in GraphQL (`reviewThreads.isResolved`), not in REST.
- **Options**: (a) issue comments only (`issues/<n>/comments`); (b) all three REST sources - issue comments, inline review comments (`pulls/<n>/comments`), review bodies and verdicts (`pulls/<n>/reviews`); (c) all three plus a GraphQL call for review-thread resolved state.
- **Recommended**: (b) - it captures the whole discussion using the paginated REST helper the tool already has (`_run_paginated_json`, `src/prinfo/gh.py:188`). (c) adds a second API dialect and a different failure mode for one boolean; it is a good follow-up, not part of this task.
- **Answer**: (c) - decided by user, overriding the recommendation. Resolved/unresolved thread state is in scope for this task, so the plan carries a GraphQL call alongside the three REST calls and maps thread state onto the inline review comments by comment id.

## Q3: Should the two new flags be usable without exporting check logs?

- **Why it matters**: `resolve_config` currently rejects `--skip-check-logs` unless `--export-commit-files` is set (`src/prinfo/config.py:52`). Adding two more export modes without touching that guard means neither new flag can be used on its own, which is the most likely way they will be used.
- **Options**: (a) leave the guard as is - the new flags only ever run alongside commit-file export; (b) relax the guard so `--skip-check-logs` is satisfied by any one of `--export-commit-files`, `--export-comments`, `--export-commit-log`.
- **Recommended**: (b) - the guard exists to stop a run that exports nothing, and that intent is preserved by widening it. Leaving it narrow would make `--export-comments --skip-check-logs` fail for no reason a user could infer.
- **Answer**: (b) - decided by user.

## Q4: What does `--export-commit-log` write when `--export-commit-files` is also set?

- **Why it matters**: Both flags read the same `pulls/<n>/commits` payload. Running them together could duplicate the API call and produce two files describing the same commits.
- **Options**: (a) always write `commit-log.json` from its own call, independent of the file export; (b) write `commit-log.json` only when `--export-commit-files` is absent, otherwise rely on `commits-manifest.json`; (c) share one fetch and write `commit-log.json` from it, reusing the already-fetched commit list when the file export ran.
- **Recommended**: (c) - one output path is predictable regardless of flag combination, and reusing the fetched list avoids a second paginated call. `commits-manifest.json` keeps its current shape and meaning, so nothing existing changes.
- **Answer**: (c) - decided by user.

## Q5: What env keys and naming do the new flags get?

- **Why it matters**: Every existing flag has a `PRINFO_*` counterpart resolved in `resolve_config`, and README documents the full list. Skipping the env keys would break the pattern; the names have to be chosen once because they become a public interface.
- **Options**: (a) `PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG`; (b) shorter `PRINFO_COMMENTS` / `PRINFO_COMMIT_LOG`.
- **Recommended**: (a) - it mirrors `PRINFO_EXPORT_COMMIT_FILES`, which is the only precedent for an export-mode toggle.
- **Answer**: (a) - decided by reading `src/prinfo/config.py:43` and `README.md` supported-env-keys list.

## Q6: Should bot and review-state noise be filtered out of the comment export?

- **Why it matters**: A PR often carries CI bot comments and `COMMENTED` reviews with an empty body. Filtering makes the transcript readable; not filtering makes the export faithful.
- **Options**: (a) export everything verbatim, record the author and `user.type` per entry so a consumer can filter; (b) drop bot comments; (c) add a `--comments-exclude-bots` flag.
- **Recommended**: (a) - the tool's job is export, not curation, and every existing exporter records rather than judges (empty check logs are recorded, not dropped). (c) is scope creep with no request behind it.
- **Answer**: (a) - decided by user.

## Q7: Does a partial failure of one comment source fail the whole run?

- **Why it matters**: The three endpoints fail independently - a repo can 404 on one. `main` already treats check-log and commit-file export as independently failable (`src/prinfo/cli.py:80-95`), so the new modes need a stated position.
- **Options**: (a) any endpoint failure aborts the comment export; (b) record the failure per source in the manifest and export what succeeded, matching how skipped checks and skipped commit files are handled.
- **Recommended**: (b) - it matches the established skipped-record convention and the existing per-mode error isolation in `main`.
- **Answer**: (b) - decided by user.

## Resolution Summary

| ID | Status | Carried by |
| -- | ------ | ---------- |
| Q1 | Answered | REQ-2, REQ-3 |
| Q2 | Answered | REQ-2, REQ-7 |
| Q3 | Answered | REQ-5 |
| Q4 | Answered | REQ-4 |
| Q5 | Answered | REQ-5 |
| Q6 | Answered | REQ-2 |
| Q7 | Answered | REQ-6 |
