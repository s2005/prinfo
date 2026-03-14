---
name: prinfo
description: Use this skill when the user wants to run, troubleshoot, or interpret the prinfo CLI for GitHub pull request checks. Activate for requests about exporting PR check logs, GitHub Actions job logs, manifest.json, skipped checks, gh authentication context, or prinfo command arguments and env-file settings.
---

# prinfo Skill

Run and interpret `prinfo`, a Python CLI that exports GitHub pull request
check logs through the GitHub CLI and can also export PR commit files into
per-commit folders.

## Use This Skill When

- Export PR check logs for a specific pull request.
- Export PR commit files for a specific pull request.
- Build the right `prinfo` command for a repo, PR number, or auth context.
- Troubleshoot missing logs, skipped checks, or `gh` authentication problems.
- Explain the files written by `prinfo`, especially `manifest.json`,
  `commits-manifest.json`, and per-commit `_commit.json` files.

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
7. If commit export is requested, decide whether the user wants commit-only
   output with `--skip-check-logs`.
8. Run `uv run prinfo ...` from this repository when possible.
9. Inspect `manifest.json`, `commits-manifest.json`, exported logs,
   per-commit folders, and skipped entries.
10. Explain any failure in one of these buckets:
   configuration, repository resolution, PR checks not found, unsupported
   checks, log download failure, commit listing failure, or commit file
   download failure.

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

## Bundled References

- Read `references/commands.md` for command recipes.
- Read `references/outputs.md` when interpreting generated files.
- Read `references/troubleshooting.md` for common failure modes.
