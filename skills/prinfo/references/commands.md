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

Remember that explicit CLI flags override values from the env file.

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
