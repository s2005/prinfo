# Implementation Plan

## Proposed changes

1. Add an explicit CLI/config switch for commit-file export

- Keep the existing PR check-log export flow intact.
- Add a new `--export-commit-files` flag so commit export is additive rather
  than a breaking behavior change.
- Allow env-file control through `PRINFO_EXPORT_COMMIT_FILES`.

1. Extend the GitHub client for PR commit inspection

- Add a method to list commits belonging to a PR.
- Add a method to fetch the files changed in a specific commit.
- Add a binary-safe file download helper so exported commit files are written
  exactly as returned by GitHub.

1. Export per-commit folders

- Write commit files under `commits/<sha>/...` inside the chosen output
  directory.
- Preserve repository-relative paths inside each commit folder.
- Write a per-commit manifest plus a root commit manifest that lists commits,
  exported files, and skipped files.

1. Keep execution resilient when logs are missing

- If `--export-commit-files` is enabled and PR check-log export fails because
  there are no exportable logs, continue with commit export.
- Return success when at least one requested export path succeeds.

1. Update tests and docs

- Cover config parsing, GitHub client parsing, and exporter output layout.
- Update README usage and output documentation for the new commit export mode.

## Expected file impact

- `src/prinfo/cli.py`
- `src/prinfo/config.py`
- `src/prinfo/exporter.py`
- `src/prinfo/gh.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_exporter.py`
- `tests/test_gh.py`
- `README.md`

## Output shape

- Existing log export remains at the output root.
- Commit export writes:
  - `commits/<commit-sha>/...`
  - `commits/<commit-sha>/_commit.json`
  - `commits-manifest.json`
