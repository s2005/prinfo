# PRD: Document Every PRINFO Env Key

## Objective

Bring the two env-key lists in `README.md` and `skills/prinfo/references/commands.md` back into
agreement with the keys `resolve_config` actually reads, and document `PRINFO_ENV_FILE` - which no
document mentions today - in a way that reflects how it is really read. A user reading either
document should be able to name every input `prinfo` accepts and know where to put it.

## Background

`prinfo` resolves configuration in `resolve_config` (`src/prinfo/config.py:34`). Two distinct
mechanisms are at work, and the documentation collapses them into one.

Every key except one is read from `env_values`, which `_load_env_values` builds from the env file
through `dotenv_values` (`src/prinfo/config.py:37`). These keys are read from the file only - a
`PRINFO_PR=5` exported in the shell has no effect, and nothing reports that.

`PRINFO_ENV_FILE` is the exception. `_resolve_env_file` reads it from `env_source`, the process
environment (`src/prinfo/config.py:93`), because it selects which env file to load. It therefore
cannot be set inside that file. It is the env counterpart of `--env-file`.

The two lists have drifted from `config.py` and from each other:

| Key | Read by `resolve_config` | In `README.md` | In `commands.md` |
| --- | ------------------------ | -------------- | ---------------- |
| `PRINFO_PR` | Yes, env file | Yes | Yes |
| `PRINFO_REPO` | Yes, env file | Yes | Yes |
| `PRINFO_OUTPUT_DIR` | Yes, env file | Yes | Yes |
| `PRINFO_EXPORT_COMMIT_FILES` | Yes, env file | Yes | No |
| `PRINFO_SKIP_CHECK_LOGS` | Yes, env file | Yes | No |
| `PRINFO_GH_HOST` | Yes, env file | Yes | Yes |
| `PRINFO_GH_TOKEN` | Yes, env file | Yes | Yes |
| `PRINFO_GH_CONFIG_DIR` | Yes, env file | Yes | Yes |
| `PRINFO_LOG_LEVEL` | Yes, env file | Yes | Yes |
| `PRINFO_ENV_FILE` | Yes, process environment | No | No |

The row counts above describe the repository default branch. The `comments-commit-log` task adds
`PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG`, which land in `README.md` and
`commands.md` with it. This task is written against whatever set `resolve_config` reads at the time
it is implemented, so it stays correct whether or not that work has merged first.

Both gaps were found by a documentation drift check run while closing the `comments-commit-log`
task, and were deliberately left out of it because that task's requirements did not cover them.

## Requirements

### REQ-1: `README.md` lists every env-file key

The supported-env-keys list in `README.md` contains exactly the set of keys `resolve_config` reads
from `env_values`, with no key missing and no key listed that the code does not read.
`PRINFO_ENV_FILE` is not in this list, because it is not read from the env file; REQ-3 covers it.

### REQ-2: `skills/prinfo/references/commands.md` lists the same keys

The supported-keys list in `skills/prinfo/references/commands.md` contains the same set as REQ-1.
The file keeps its own copy of the list rather than pointing at `README.md`, because the skill is
loaded on its own by an agent that may never read `README.md`.

The existing sentence "There is currently no env-file key for `--skip-empty-logs`." is accurate -
`skip_empty_logs` is read from the CLI namespace alone (`src/prinfo/config.py:46`) - and is kept.

### REQ-3: `PRINFO_ENV_FILE` is documented as a process-environment variable

Both documents gain a short subsection covering `PRINFO_ENV_FILE` that states:

- it is read from the process environment, not from the env file,
- it names the env file the keys in the list are read from, so it cannot be set inside that file,
- it is the env counterpart of `--env-file`, and `--env-file` wins when both are given,
- when neither is given, `prinfo` falls back to an env file named `.env` in the current directory
  when one exists.

Every statement above is asserted by `_resolve_env_file` (`src/prinfo/config.py:92-102`).

### REQ-4: Both documents say the listed keys come from the env file

Each list carries one sentence stating that its keys are read from the env file and not from
exported shell variables, so a reader cannot mistake them for ordinary environment variables.

## Non-Requirements

- **No automated drift test.** A test reading `PRINFO_*` out of `src/prinfo/config.py` and asserting
  each key is documented was considered and declined by the user in Q3 of `open_questions.md`. It
  would prevent this class of gap recurring and is worth its own task; it is not part of this one.
- No change to `src/prinfo/config.py` or any other source file. The code is correct; only the
  documentation is wrong.
- No new env key, and no env key for `--skip-empty-logs`.
- No `.env.example` file. The repository has none and adding one is a separate decision.
- No change to `INSTALL_SKILL.md`, `skills/prinfo/SKILL.md`, `skills/prinfo/references/outputs.md` or
  `skills/prinfo/references/troubleshooting.md`, none of which carries an env-key list.

## Acceptance Criteria

- **AC-1** - the supported-env-keys list in `README.md` matches, exactly and with no extras, the set
  of keys read from `env_values` in `src/prinfo/config.py` (REQ-1)
- **AC-2** - the supported-keys list in `skills/prinfo/references/commands.md` matches that same set,
  and the `--skip-empty-logs` sentence is still present (REQ-2)
- **AC-3** - both documents carry a `PRINFO_ENV_FILE` subsection stating it is read from the process
  environment, that it names the env file, that `--env-file` takes precedence, and that `.env` is the
  fallback (REQ-3)
- **AC-4** - both documents state that the listed keys are read from the env file rather than from
  exported shell variables (REQ-4)
- **AC-5** - `markdownlint-cli2 "**/*.md" "#node_modules"` reports no findings (REQ-1, REQ-2, REQ-3,
  REQ-4)
- **AC-6** - `uv run pytest` and `uv run ruff check .` pass unchanged, and `git diff` touches no file
  under `src/` or `tests/` (REQ-1, REQ-2, REQ-3, REQ-4)

## Deliverables

| Deliverable | Type |
| ----------- | ---- |
| README.md | Update |
| skills/prinfo/references/commands.md | Update |
