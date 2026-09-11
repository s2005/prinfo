# Verification Plan: Document Every PRINFO Env Key

## Purpose

Proves that both env-key lists match the keys `resolve_config` actually reads, that
`PRINFO_ENV_FILE` is documented as the process-environment variable it is rather than as an env-file
key, and that a documentation-only task changed no behaviour. Every command below is the project's
real gate, taken from the Development section of `README.md`.

## Pre-Implementation Verification

### Existing Tests Pass

```bash
uv run pytest
```

Expected: all pass. Record the count so the post-implementation run can be compared against it.

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

### Current Documentation Gap

```bash
uv run python -c "import re,pathlib; cfg=pathlib.Path('src/prinfo/config.py').read_text(encoding='utf-8'); code=set(re.findall(r'env_values\.get\(\"(PRINFO_[A-Z_]+)\"', cfg)); rd=set(re.findall(r'PRINFO_[A-Z_]+', pathlib.Path('README.md').read_text(encoding='utf-8'))); cm=set(re.findall(r'PRINFO_[A-Z_]+', pathlib.Path('skills/prinfo/references/commands.md').read_text(encoding='utf-8'))); print('README missing:', sorted(code-rd)); print('commands.md missing:', sorted(code-cm))"
```

Expected before the change: `commands.md missing` names at least `PRINFO_EXPORT_COMMIT_FILES` and
`PRINFO_SKIP_CHECK_LOGS`. This is the before state for AC-2.

```bash
grep -c "PRINFO_ENV_FILE" README.md skills/prinfo/references/commands.md
```

Expected before the change: `0` for both files. This is the before state for AC-3.

The project configures no coverage threshold in `pyproject.toml`, so no coverage baseline table is
kept.

## Post-Implementation Verification

### Per-Phase Verification

#### Phase 1: README env key reference

Covers REQ-1, REQ-3 and REQ-4.

```bash
uv run python -c "import re,pathlib; cfg=pathlib.Path('src/prinfo/config.py').read_text(encoding='utf-8'); code=set(re.findall(r'env_values\.get\(\"(PRINFO_[A-Z_]+)\"', cfg)); doc=set(re.findall(r'PRINFO_[A-Z_]+', pathlib.Path('README.md').read_text(encoding='utf-8'))); print('missing from README:', sorted(code-doc)); print('in README only:', sorted(doc-code-{'PRINFO_ENV_FILE'}))"
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: both difference lists print empty, and the Markdown linter reports no findings.

Then read `src/prinfo/config.py:92-102` and confirm the new subsection asserts nothing
`_resolve_env_file` does not do: process-environment origin, `--env-file` precedence, and the `.env`
fallback.

#### Phase 2: Skill command reference

Covers REQ-2, REQ-3 and REQ-4.

```bash
uv run python -c "import re,pathlib; cfg=pathlib.Path('src/prinfo/config.py').read_text(encoding='utf-8'); code=set(re.findall(r'env_values\.get\(\"(PRINFO_[A-Z_]+)\"', cfg)); doc=set(re.findall(r'PRINFO_[A-Z_]+', pathlib.Path('skills/prinfo/references/commands.md').read_text(encoding='utf-8'))); print('missing from commands.md:', sorted(code-doc))"
grep -c "skip-empty-logs" skills/prinfo/references/commands.md
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: the difference list prints empty, the `--skip-empty-logs` sentence is still present, and
the Markdown linter reports no findings.

### Linter

```bash
uv run ruff check .
```

Expected: clean, with no findings introduced by this task.

### Markdown Linter

```bash
markdownlint-cli2 "**/*.md" "#node_modules"
```

Expected: clean across `README.md`, the skill files and the five task files.

### Regression Check

```bash
uv run pytest
```

Expected: all pass, with the same test count as the pre-implementation baseline, because no source
file changed.

### Source Untouched Check

```bash
git diff --name-only main -- src tests
```

Expected: no output. A documentation task that touched a source or test file has exceeded its scope.

## Final Acceptance Verification

The feature can be accepted when all items are true:

- [x] AC-1 - the supported-env-keys list in `README.md` matches the set read from `env_values` in `src/prinfo/config.py`, with no missing key and no extra - verified by: Phase 1 verification
- [x] AC-2 - the supported-keys list in `skills/prinfo/references/commands.md` matches that same set and the `--skip-empty-logs` sentence survives - verified by: Phase 2 verification
- [x] AC-3 - both documents carry a `PRINFO_ENV_FILE` subsection stating process-environment origin, `--env-file` precedence and the `.env` fallback - verified by: Phase 1 and Phase 2 verification, read against `src/prinfo/config.py:92-102`
- [x] AC-4 - both documents state the listed keys are read from the env file rather than from exported shell variables - verified by: Phase 1 and Phase 2 verification
- [x] AC-5 - `markdownlint-cli2 "**/*.md" "#node_modules"` reports no findings - verified by: Markdown Linter section
- [x] AC-6 - `uv run pytest` and `uv run ruff check .` pass unchanged and no file under `src/` or `tests/` was touched - verified by: Linter, Regression Check and Source Untouched Check sections
