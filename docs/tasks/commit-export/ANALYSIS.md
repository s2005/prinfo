# Analysis

## Current behavior

`prinfo` currently exports GitHub Actions check logs for a PR and writes one
log file per job plus `manifest.json`. It does not inspect the PR commit list
or export repository files for those commits.

## Gaps relative to the request

1. No PR commit enumeration

- `src/prinfo/gh.py` only exposes repository detection, check discovery, and
  job-log download helpers.
- There is no client path for `pulls/<pr>/commits` or `commits/<sha>`.

1. No file-export workflow for commits

- `src/prinfo/exporter.py` only knows how to save `.log` files for Actions
  jobs.
- There is no output structure for commit folders or commit manifests.

1. CLI is currently single-purpose

- `src/prinfo/cli.py` assumes a single export result and treats missing log
  exports as a hard failure.
- That would block the new commit export path on PRs that have commits but no
  exportable checks unless the control flow is adjusted.

## Design choices

1. Make commit export additive

- A dedicated flag avoids silently changing the existing contract for users
  who only want check logs.

1. Use commit SHA as the folder name

- This directly matches the request and guarantees uniqueness without extra
  sanitization logic.

1. Preserve repository-relative paths inside each commit folder

- This keeps the exported files useful for inspection and comparison.

1. Add structured manifests for commit export

- A root commit manifest provides a PR-level commit list.
- A per-commit manifest keeps file-level metadata close to the exported files.

## Risks to handle

- Deleted files cannot be downloaded at the target commit SHA and must be
  represented as skipped entries in commit metadata.
- Some files may fail to download and should not abort the whole export when
  other commit files can still be written.
- Binary content should be handled without text-decoding corruption.
