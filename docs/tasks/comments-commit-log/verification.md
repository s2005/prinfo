# Verification Plan: Export PR Comments and Commit Log

## Purpose

Proves that `--export-comments` and `--export-commit-log` behave as specified in `PRD.md`, that the relaxed `--skip-check-logs` guard did not weaken the "never run an export that exports nothing" rule, and that the existing check-log and commit-file exports are unchanged. Every command below is the project's real gate, taken from the Development section of `README.md`.

## Pre-Implementation Verification

### Existing Tests Pass

```bash
uv run pytest
```

Expected: all pass. Record the test count so the post-implementation run can be compared against it.

### Linter Baseline

```bash
uv run ruff check .
```

Expected: clean. Any finding here is pre-existing and out of scope.

### Markdown Baseline

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean.

### Current Output Shape

```bash
uv run prinfo --help
```

Expected: no `--export-comments` and no `--export-commit-log` in the output. This is the before state for AC-5.

The project configures no coverage threshold in `pyproject.toml`, so no coverage baseline table is kept.

## Post-Implementation Verification

### Per-Phase Verification

#### Phase 1: Config and CLI surface

Covers REQ-5.

```bash
uv run pytest tests/test_config.py tests/test_cli.py
uv run prinfo --help
```

Expected: tests pass; help output lists `--export-comments` and `--export-commit-log` with their help text.

```bash
uv run prinfo --pr 1 --repo octo/repo --skip-check-logs
```

Expected: exit code 1 and a `ConfigurationError` message naming all three export flags and all three env keys.

#### Phase 2: gh client comment access

Covers REQ-1 and REQ-7.

```bash
uv run pytest tests/test_gh.py
uv run ruff check src tests
```

Expected: every new parser test passes, the malformed-entry test shows `GhCliError` with the endpoint in the message, and the GraphQL test yields `ReviewThread` records whose `comment_ids` came from `databaseId`.

#### Phase 3: Comment export

Covers REQ-2, REQ-3, REQ-6 and REQ-7.

```bash
uv run pytest tests/test_exporter.py -k comments
```

Expected: `comments.json` holds all four sources with per-source counts; `comments.md` is ordered by timestamp with the untimestamped entry last; a single failing source is recorded in `skipped_sources` while the rest export; a total failure raises `ExportError`; thread state lands on matching review comments only.

#### Phase 4: Commit log export

Covers REQ-4.

```bash
uv run pytest tests/test_exporter.py -k commit
```

Expected: the commit-log-only test records zero `download_commit_file` calls; the combined test records exactly one `list_pr_commits` call and finds both `commit-log.json` and `commits-manifest.json`; the pre-existing commit-file tests pass unchanged.

#### Phase 5: Orchestration and docs

Covers REQ-6 and REQ-8.

```bash
uv run pytest tests/test_cli.py
uv run prinfo --version
```

Expected: partial-failure test returns 0, total-failure test returns 1, and `--version` reports `prinfo 0.4.0`.

### Linter

```bash
uv run ruff check .
```

Expected: clean, with no findings introduced by this task and no suppression directive added to source.

### Markdown Linter

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean across `README.md`, the skill files and the five task files.

### Regression Check

```bash
uv run pytest
```

Expected: all pass, with a test count higher than the pre-implementation baseline and no previously passing test removed or weakened.

### Live Smoke Check

Run against a real pull request the user has access to, into a scratch directory outside the repository:

```bash
uv run prinfo --repo owner/repo --pr <n> --export-comments --export-commit-log --skip-check-logs --output-dir <scratch>/pr-<n>
```

Expected: `comments.json`, `comments.md` and `commit-log.json` written; no `commits/` directory created; the transcript readable end to end; `--log-level DEBUG` showing four comment-source calls and exactly one commits call.

## Final Acceptance Verification

The feature can be accepted when all items are true:

- [x] AC-1 - the three REST client methods parse a fake paginated payload into the documented fields and raise `GhCliError` naming the endpoint on a non-object entry - verified by: Phase 2 verification, `uv run pytest tests/test_gh.py`
- [x] AC-2 - `comments.json` holds every record from all three REST sources with `author`, `author_type` and per-source `counts` - verified by: Phase 3 verification
- [x] AC-3 - `comments.md` sections are in timestamp order with the untimestamped entry last and no exception raised - verified by: Phase 3 verification
- [x] AC-4 - `--export-commit-log` alone writes `commit-log.json` and downloads nothing; combined with `--export-commit-files` both outputs exist and the commits endpoint is called once - verified by: Phase 4 verification
- [x] AC-5 - `build_parser` accepts both flags and `resolve_config` maps both env keys with CLI winning - verified by: Phase 1 verification
- [x] AC-6 - `--skip-check-logs` is accepted with any single export mode and rejected with none set, the message naming all three - verified by: Phase 1 verification, including the live `ConfigurationError` command
- [x] AC-7 - one failing comment source leaves the others exported and is recorded with a `reason_code`; all sources failing raises `ExportError` - verified by: Phase 3 verification
- [x] AC-8 - `main` returns 0 on partial failure and 1 when every requested mode fails - verified by: Phase 5 verification
- [x] AC-9 - `list_pr_review_threads` parses paginated GraphQL into `ReviewThread` records and thread state lands on matching review comments, unmatched staying `None` - verified by: Phase 2 and Phase 3 verification
- [x] AC-10 - a GraphQL failure is recorded in `skipped_sources` while all three REST sources still export - verified by: Phase 3 verification
- [x] AC-11 - `README.md` documents both flags, both env keys and all three new output files, and the Markdown linter is clean - verified by: Markdown Linter section
- [x] AC-12 - `uv run ruff check .` and `uv run pytest` both pass - verified by: Linter and Regression Check sections
