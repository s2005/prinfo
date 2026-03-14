## prinfo

`prinfo` is a cross-platform Python CLI that uses GitHub CLI (`gh`) to export pull request check logs into a local folder. The first version focuses on GitHub Actions-backed PR checks and writes one log file per check job plus a manifest.

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- GitHub CLI (`gh`) installed and authenticated for the target repository

### Quick start

```bash
uv sync --dev
uv run prinfo --repo owner/repo --pr 123 --output-dir artifacts/pr-123
```

You can also load configuration from an env file:

```bash
uv run prinfo --env-file some.env
```

Supported env keys:

- `PRINFO_PR`
- `PRINFO_REPO`
- `PRINFO_OUTPUT_DIR`
- `PRINFO_GH_HOST`
- `PRINFO_GH_TOKEN`
- `PRINFO_GH_CONFIG_DIR`
- `PRINFO_LOG_LEVEL`

CLI arguments override env-file values.

### Multiple GitHub accounts

`prinfo` does not mutate your global `gh` login state. Instead, it supports account selection by passing either:

- `PRINFO_GH_TOKEN` / `--gh-token`
- `PRINFO_GH_CONFIG_DIR` / `--gh-config-dir`

That lets you point `prinfo` at a different authenticated `gh` context per run.

### Output

The command writes:

- one `*.log` file for each exported GitHub Actions job
- `manifest.json` with exported and skipped checks

Checks that are not backed by GitHub Actions jobs are skipped and recorded in the manifest.

### Development

```bash
uv sync --dev
uv run pytest
```
