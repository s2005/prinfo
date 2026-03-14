# prinfo

`prinfo` is a cross-platform Python CLI that uses GitHub CLI (`gh`) to
export pull request check logs into a local folder. It can also export the
files touched by each PR commit into per-commit folders. The current
implementation focuses on GitHub-backed PR metadata and writes manifests for
both export modes.

This repository also includes an Agent Skill for running, troubleshooting,
and interpreting `prinfo`. Installation instructions are in
[INSTALL_SKILL.md](./INSTALL_SKILL.md).

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- GitHub CLI (`gh`) installed and authenticated for the target repository

## Install globally

To make `prinfo` available as a shell command outside this repository, install it as a
global `uv` tool from the checkout:

```bash
uv tool install --editable .
```

That exposes the `prinfo` command from uv's global tool bin directory while keeping it
linked to the local repository for editable development.

To install without cloning the repository first, install directly from Git:

```bash
uv tool install git+https://github.com/s2005/prinfo.git
```

That installs `prinfo` from the latest commit on the repository's default branch.

## Quick start

```bash
uv sync --dev
uv run prinfo --repo owner/repo --pr 123 --output-dir artifacts/pr-123
```

If you want empty job logs to appear only in `manifest.json` and not as zero-byte files:

```bash
uv run prinfo --repo owner/repo --pr 123 --skip-empty-logs
```

To export commit folders alongside the check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files
```

To export only commit folders and skip PR check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files --skip-check-logs
```

You can also load configuration from an env file:

```bash
uv run prinfo --env-file some.env
```

Supported env keys:

- `PRINFO_PR`
- `PRINFO_REPO`
- `PRINFO_OUTPUT_DIR`
- `PRINFO_EXPORT_COMMIT_FILES`
- `PRINFO_SKIP_CHECK_LOGS`
- `PRINFO_GH_HOST`
- `PRINFO_GH_TOKEN`
- `PRINFO_GH_CONFIG_DIR`
- `PRINFO_LOG_LEVEL`

CLI arguments override env-file values.

## Multiple GitHub accounts

`prinfo` does not mutate your global `gh` login state. Instead, it
supports account selection by passing either:

- `PRINFO_GH_TOKEN` / `--gh-token`
- `PRINFO_GH_CONFIG_DIR` / `--gh-config-dir`

That lets you point `prinfo` at a different authenticated `gh` context per run.

## Output

The command writes:

- one `*.log` file for each exported GitHub Actions job
- `manifest.json` with exported and skipped checks
- optional `commits/<commit-sha>/...` folders when `--export-commit-files` is enabled
- optional `commits/<commit-sha>/_commit.json` per commit
- optional `commits-manifest.json` with the PR commit list and per-commit summaries

Checks that are not backed by GitHub Actions jobs are skipped and
recorded in the manifest.

When `--skip-empty-logs` is enabled, empty logs are still recorded in the
manifest but their `path` is left empty and no zero-byte file is written.

When `--export-commit-files` is enabled, commit export still runs even if the
PR has no downloadable Actions logs. Removed files are recorded in commit
metadata as skipped because they cannot be downloaded at the target commit SHA.

When `--skip-check-logs` is enabled, `prinfo` performs a commit-only export.

## Skill

The `prinfo` skill lives in `skills/prinfo` and is intended for agent
workflows around:

- building the right `prinfo` command
- choosing `gh` authentication context
- interpreting `manifest.json`
- troubleshooting skipped checks and missing logs

See [INSTALL_SKILL.md](./INSTALL_SKILL.md) for installation steps for
Claude Code, VS Code, Cursor, and Codex.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

Markdown linting uses the repo-local
[.markdownlint-cli2.jsonc](./.markdownlint-cli2.jsonc) configuration and a
globally installed `markdownlint-cli2` binary:

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

## CI

GitHub Actions runs the following checks on pull requests:

- `ruff`
- `pytest`
- `markdownlint-cli2`
- CLI help smoke test on Windows, Linux, and macOS
