# PRD: prinfo v0.1

## Objective

Build a cross-platform Python CLI application named `prinfo` that exports pull request check logs through GitHub CLI and saves them to a chosen local folder. The tool must run on Windows, Linux, and macOS, use `uv` for dependency management, and be structured for future extension.

## Problem Statement

Pull request checks often fail in CI systems, but gathering all related logs across multiple checks is repetitive. A small CLI should allow a user to point at a PR, select the GitHub authentication context to use, and export the available logs into a predictable folder for later review or automation.

## Scope

### In scope for v0.1

- Python package managed with `uv`
- CLI entry point implemented with `argparse`
- Runtime logging implemented with the standard `logging` module
- Explicit startup failure when `gh` is not installed or not on `PATH`
- Configuration from command-line arguments and optional env files
- Support for multiple GitHub authentication contexts via token or `gh` config directory
- PR check discovery through `gh pr view --json statusCheckRollup`
- Log export for GitHub Actions job-backed checks using `gh api`
- Manifest file describing exported and skipped checks
- Unit tests with `pytest`
- Git hygiene via `.gitignore`

### Out of scope for v0.1

- Full support for third-party CI providers that are not GitHub Actions
- Parallel log downloads
- Retry/backoff logic for transient API failures
- Packaging and publishing to PyPI
- Rich terminal UI

## User Stories

- As a developer, I want to export all available PR check logs into one folder so I can inspect failures offline.
- As a developer with multiple GitHub accounts, I want to choose the auth context for a run without changing my global `gh` state.
- As a maintainer, I want deterministic output files and a manifest so the CLI can be used in scripts.

## Functional Requirements

1. The CLI must expose a `prinfo` command.
2. The CLI must accept a PR number through `--pr` or `PRINFO_PR`.
3. The CLI should accept a repository through `--repo` or `PRINFO_REPO`; if omitted, it should try `gh repo view --json nameWithOwner`.
4. The CLI should accept an output directory through `--output-dir` or `PRINFO_OUTPUT_DIR`; if omitted, it should default to `artifacts/pr-<number>`.
5. The CLI must accept an optional env file through `--env-file`, with `.env` auto-loaded when present.
6. The CLI must support alternate GitHub authentication via:
   - `--gh-token` / `PRINFO_GH_TOKEN`
   - `--gh-config-dir` / `PRINFO_GH_CONFIG_DIR`
   - `--gh-host` / `PRINFO_GH_HOST`
7. CLI arguments must override env-file values.
8. The CLI must fail with a clear error when `gh` is missing.
9. The CLI must inspect PR checks and identify GitHub Actions-backed jobs by parsing the check details URL.
10. The CLI must download one log file per supported check job and save it with a sanitized file name.
11. The CLI must write `manifest.json` describing exported logs and skipped checks.
12. The CLI must return a non-zero exit code when no logs can be exported.

## Non-Functional Requirements

- Must run on Windows, Linux, and macOS.
- Must use standard-library-friendly implementation choices where practical.
- Must avoid mutating the user’s global `gh` auth state during account selection.
- Must keep env files out of version control.
- Must be testable without live GitHub API calls.

## CLI Proposal

```text
prinfo --pr 123 --repo owner/repo --output-dir artifacts/pr-123
prinfo --env-file some.env
```

Supported flags:

- `--pr`
- `--repo`
- `--output-dir`
- `--env-file`
- `--gh-host`
- `--gh-token`
- `--gh-config-dir`
- `--log-level`

## Env File Proposal

```dotenv
PRINFO_PR=123
PRINFO_REPO=owner/repo
PRINFO_OUTPUT_DIR=artifacts/pr-123
PRINFO_GH_HOST=github.com
PRINFO_GH_TOKEN=ghp_xxx
PRINFO_GH_CONFIG_DIR=/path/to/gh-config
PRINFO_LOG_LEVEL=INFO
```

This example is documentation only. Real env files remain untracked.

## Technical Design

### Modules

- `prinfo.cli`: argument parsing, logging setup, process exit code
- `prinfo.config`: env-file loading and config resolution
- `prinfo.gh`: `gh` subprocess wrapper, repo parsing, PR check retrieval, job-log download
- `prinfo.exporter`: log export workflow, manifest generation, file naming

### Log Export Flow

1. Resolve config from CLI args and env file.
2. Verify `gh` is installed.
3. Resolve the repository, either directly or from the current directory.
4. Query PR checks from `gh pr view --json statusCheckRollup`.
5. Parse GitHub Actions job IDs from check URLs.
6. Download each job log from `repos/{owner}/{repo}/actions/jobs/{job_id}/logs`.
7. Save each log file and write `manifest.json`.
8. Return success if at least one log was exported.

## Testing Strategy

- Unit tests for config precedence and defaults
- Unit tests for repository and Actions URL parsing
- Unit tests for export behavior using a fake `gh` client
- CLI smoke tests for `--help` and a public PR scenario during manual verification

## Risks and Limitations

- Non-Actions checks may not provide log artifacts or stable URLs, so they are skipped in v0.1.
- Fine-grained PAT limitations in `gh` can affect some commands in certain environments.
- Large logs are written fully to disk and may require future streaming support.

## Future Enhancements

- Third-party CI adapters
- Parallel downloads
- Retry handling and rate-limit awareness
- Filtering by failed checks only
- Structured output formats beyond raw `.log`
