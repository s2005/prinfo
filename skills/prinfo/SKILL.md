---
name: prinfo
description: Use this skill when the user wants to run, troubleshoot, or interpret the prinfo CLI for GitHub pull request checks. Activate for requests about exporting PR check logs, GitHub Actions job logs, manifest.json, skipped checks, gh authentication context, prinfo command arguments and env-file settings, PR comments, review threads, resolved state, comments.json, comments.md, or commit-log.json.
---

# prinfo Skill

Run and interpret `prinfo`, a Python CLI that exports GitHub pull request
check logs through the GitHub CLI and can also export PR commit files into
per-commit folders, export the PR review discussion, and export the commit
log.

## Use This Skill When

- Export PR check logs for a specific pull request.
- Export PR commit files for a specific pull request.
- Export the PR review discussion (issue comments, review comments, reviews,
  and review-thread resolved state) for a specific pull request.
- Export the PR commit log for a specific pull request.
- Build the right `prinfo` command for a repo, PR number, or auth context.
- Troubleshoot missing logs, skipped checks, or `gh` authentication problems.
- Explain the files written by `prinfo`, especially `manifest.json`,
  `commits-manifest.json`, per-commit `_commit.json` files, `comments.json`,
  `comments.md`, and `commit-log.json`.

## Quick Workflow

1. Confirm the PR number.
2. Decide whether the repository can be detected from the current checkout.
   If not, require `--repo`.
3. Choose the auth mode:
   - existing `gh` login
   - `--gh-token` or `PRINFO_GH_TOKEN`
   - `--gh-config-dir` or `PRINFO_GH_CONFIG_DIR`
4. Choose the output directory. Default to `artifacts/pr-<pr-number>` when the
   user does not specify one.
5. Decide whether empty logs should be written as zero-byte files or recorded
   only in `manifest.json` with `--skip-empty-logs`.
6. Decide whether commit export is needed with `--export-commit-files`.
7. Decide whether the PR review discussion is needed with `--export-comments`.
8. Decide whether the commit log alone is needed with `--export-commit-log`.
9. If any export mode is requested, decide whether the user wants an
   export-only run with `--skip-check-logs`.
10. Run `uv run prinfo ...` from this repository when possible.
11. Inspect `manifest.json`, `commits-manifest.json`, exported logs,
    per-commit folders, `comments.json`, `comments.md`, `commit-log.json`,
    and skipped entries.
12. Explain any failure in one of these buckets:
    configuration, repository resolution, PR checks not found, unsupported
    checks, log download failure, commit listing failure, commit file
    download failure, a skipped comment source, a failed GraphQL
    review-thread call, or no export mode producing a result.

## Critical Constraints

- Export only checks backed by GitHub Actions jobs.
- Export commit files into `commits/<sha>/...` when commit export mode is used.
- Treat checks without an Actions `job_id` as skipped, not exportable.
- Expect `HTTP 404` or `Not Found` during log download when GitHub exposes a
  check but no downloadable job log; treat that as a skipped check.
- Treat removed commit files as skipped metadata entries rather than writable
  files.
- Remember that CLI arguments override env-file values.
- Remember that `prinfo` does not mutate the user's global `gh` login state.
- Use `OWNER/REPO` for GitHub.com or `HOST/OWNER/REPO` for GitHub Enterprise.
- Comments are exported verbatim, with no bot filtering.
- Review-thread resolved state comes from a GraphQL call and may be absent;
  when it fails, every review comment is left with `is_resolved` unset.
- `--export-commit-log` downloads no file content, only commit metadata.
- `--skip-check-logs` needs at least one export mode
  (`--export-commit-files`, `--export-comments`, or `--export-commit-log`).

## Working Rules

- Prefer exact commands over abstract advice.
- State assumptions when `--repo`, auth mode, or output directory are inferred.
- If `uv run prinfo` is unavailable, fall back to an installed `prinfo`
  executable only if the environment already provides it.
- If the user asks why a check was skipped, inspect the manifest before guessing.
- If the user asks why nothing exported, verify whether every check was
  non-Actions, missing a downloadable log, or whether commit export was the
  only requested mode.
- If the user asks about empty logs, inspect `has_log_content`,
  `empty_log_reason`, and `saved` in the manifest before concluding the export
  failed.
- If the user asks about deleted or renamed files in commit export, inspect the
  per-commit `_commit.json` manifest before guessing.
- If the user asks why a comment export looks incomplete, inspect
  `skipped_sources` in `comments.json` before concluding the export failed.
- If the user wants commit history rather than file content, choose
  `--export-commit-log` over `--export-commit-files`.

## Bundled References

- Read `references/commands.md` for command recipes.
- Read `references/outputs.md` when interpreting generated files.
- Read `references/troubleshooting.md` for common failure modes.
