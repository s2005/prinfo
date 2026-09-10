# Command Recipes

Use these commands when the user needs an exact `prinfo` invocation.

## Local repo with auto-detected repository

Run from a checkout of the target repository:

```bash
uv run prinfo --pr 123
```

Use this only when `gh repo view` in the current directory can resolve the
repository.

## Explicit repository and output directory

Use this when running outside the target checkout or when repository detection
would be ambiguous:

```bash
uv run prinfo --repo owner/repo --pr 123 --output-dir artifacts/pr-123
```

## Keep empty logs only in the manifest

Use this when the user wants skipped or empty jobs represented in
`manifest.json` without writing zero-byte `.log` files:

```bash
uv run prinfo --repo owner/repo --pr 123 --skip-empty-logs
```

## Export comments alongside check logs

Use this when the user wants the PR review discussion in addition to the
check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-comments
```

## Export comments only

Use this when the user wants only the PR review discussion and no check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-comments --skip-check-logs
```

## Export the commit log only

Use this when the user wants commit metadata without file downloads and
without check logs:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-log --skip-check-logs
```

## Export both commit modes in one run

Use this when the user wants commit metadata and per-commit files together.
The commits endpoint is requested exactly once and both outputs are built
from that single fetch:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files --export-commit-log --skip-check-logs
```

## Full export with all modes together

Use this when the user wants check logs, commit files, comments, and the
commit log in a single run:

```bash
uv run prinfo --repo owner/repo --pr 123 --export-commit-files --export-comments --export-commit-log
```

## Environment file driven run

Use this when the user already has a `.env` or wants a reusable config:

```bash
uv run prinfo --env-file .env
```

Supported keys:

- `PRINFO_PR`
- `PRINFO_REPO`
- `PRINFO_OUTPUT_DIR`
- `PRINFO_GH_HOST`
- `PRINFO_GH_TOKEN`
- `PRINFO_GH_CONFIG_DIR`
- `PRINFO_LOG_LEVEL`
- `PRINFO_EXPORT_COMMENTS`
- `PRINFO_EXPORT_COMMIT_LOG`

Remember that explicit CLI flags override values from the env file.
There is currently no env-file key for `--skip-empty-logs`.

## Alternate GitHub account with token

Use this when the user wants a per-run token without changing global `gh`
state:

```bash
uv run prinfo --repo owner/repo --pr 123 --gh-token "$GH_TOKEN"
```

## Alternate GitHub account with gh config directory

Use this when the user has a separate authenticated `gh` profile on disk:

```bash
uv run prinfo --repo owner/repo --pr 123 --gh-config-dir path/to/gh-config
```

## GitHub Enterprise

Use the explicit host when the repository is not on GitHub.com:

```bash
uv run prinfo --repo git.example.com/owner/repo --pr 123 --gh-host git.example.com
```

## Verbose troubleshooting run

Use this when the user needs more detail from the CLI:

```bash
uv run prinfo --repo owner/repo --pr 123 --log-level DEBUG
```

## Help output

Use this when the user asks for the current command surface:

```bash
uv run prinfo --help
```
