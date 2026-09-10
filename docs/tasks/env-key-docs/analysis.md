# Analysis: Document Every PRINFO Env Key

## Goal

Make `README.md` and `skills/prinfo/references/commands.md` describe every configuration input
`prinfo` accepts, and describe each one where it is actually read from. Two lists have drifted from
`src/prinfo/config.py` and from each other, and one key appears in neither.

## Current Behavior

`resolve_config` (`src/prinfo/config.py:34`) is the single place configuration is resolved. It runs
three steps in order:

1. `env_source = dict(environ or os.environ)` - the process environment.
2. `env_file = _resolve_env_file(args.env_file, env_source)` - picks the env file.
3. `env_values = _load_env_values(env_file)` - loads that file through `dotenv_values`.

Every subsequent lookup goes to `env_values`, never to `env_source`. `PRINFO_PR`, `PRINFO_REPO`,
`PRINFO_OUTPUT_DIR`, `PRINFO_EXPORT_COMMIT_FILES`, `PRINFO_SKIP_CHECK_LOGS`, `PRINFO_GH_HOST`,
`PRINFO_GH_TOKEN`, `PRINFO_GH_CONFIG_DIR` and `PRINFO_LOG_LEVEL` are all env-file keys. Exporting one
in the shell does nothing, and no warning says so.

`PRINFO_ENV_FILE` is read once, inside `_resolve_env_file` (`src/prinfo/config.py:93`), from
`env_source`. Its resolution order is:

- `args.env_file` (that is, `--env-file`) when set,
- otherwise `PRINFO_ENV_FILE` from the process environment,
- otherwise `.env` in the current directory when that file exists,
- otherwise `None`, meaning no env file and CLI arguments only.

A path given through either route that does not exist raises `ConfigurationError`
(`src/prinfo/config.py:85`).

`skip_empty_logs` is the one flag with no env counterpart at all: it is read straight from the CLI
namespace (`src/prinfo/config.py:46`).

Against that, the two documents say:

- `README.md` lists nine keys under "Supported env keys" and omits `PRINFO_ENV_FILE`.
- `skills/prinfo/references/commands.md` lists seven under "Supported keys", omitting
  `PRINFO_ENV_FILE`, `PRINFO_EXPORT_COMMIT_FILES` and `PRINFO_SKIP_CHECK_LOGS`.

Neither document says the listed keys come from a file rather than the environment.

## Feasibility

Straightforward. Both edits are additive prose in files that already have the right sections, the
facts are all readable from one 134-line module, and the only gate is the Markdown linter. There is
no code change, so there is no behaviour to regress.

The one thing to get right is the framing, not the mechanics - see REQ-3.

## Approach

### Recommended: separate the two mechanisms in both documents

Sync each list to the env-file keys, add one sentence saying those keys come from the env file, and
give `PRINFO_ENV_FILE` its own short subsection describing it as a process-environment variable that
selects the file.

| Advantages | Disadvantages |
| ---------- | ------------- |
| A reader learns where to put each key, which is the actual question the docs failed to answer | Two documents grow a subsection rather than a bullet, so the diff is larger than a one-line fix |
| `PRINFO_ENV_FILE` cannot be mistaken for something to write into the env file | The distinction has to be restated in both files, since the skill reference stays self-contained |
| The `--env-file` precedence and the `.env` fallback get written down for the first time | -- |

### Alternative: append `PRINFO_ENV_FILE` to the existing lists

Add it as one more bullet and change nothing else.

| Advantages | Disadvantages |
| ---------- | ------------- |
| Smallest possible diff | Actively misleading: the list is headed "env keys" and a reader will put it in the env file, where it is never read |
| Closes the "undocumented" gap literally | Leaves the precedence rules and the `.env` fallback undocumented |

Rejected in Q1 of `open_questions.md`: a documentation fix that produces a new wrong belief is not a
fix.

### Alternative: single source of truth in `README.md`

Delete the list from the skill reference and point at `README.md`.

| Advantages | Disadvantages |
| ---------- | ------------- |
| One list, so the two can never disagree again | The skill is loaded standalone by an agent that may never read `README.md`, which is the whole point of a bundled reference |

Rejected in Q4 of `open_questions.md`.

## Implementation Notes

- **The list is derived, not authored (REQ-1, REQ-2).** Read the keys out of
  `src/prinfo/config.py` at implementation time rather than copying the table in `PRD.md`. The
  `comments-commit-log` task adds `PRINFO_EXPORT_COMMENTS` and `PRINFO_EXPORT_COMMIT_LOG`; whether
  those are present depends on merge order, and the requirement is stated against the code for
  exactly that reason.
- **Two distinct lookups (REQ-3).** The line that matters is `env_values.get(...)` versus
  `env_source.get(...)`. Only `PRINFO_ENV_FILE` uses the second. Grepping for `PRINFO_` alone does
  not distinguish them, so check which dictionary each lookup reads.
- **Do not restate the guard message.** The `--skip-check-logs` error text in
  `src/prinfo/config.py:64-68` also contains `PRINFO_*` names. Those are error-message content, not
  a lookup, and must not be mistaken for keys the resolver reads.
- **Keep the `--skip-empty-logs` sentence (REQ-2).** It is true and it answers a real question. It is
  easy to delete by accident while rewriting the surrounding list.
- **Heading uniqueness.** Both files must stay MD024-clean. `README.md` has no heading named for the
  env file yet; `commands.md` already has `## Environment file driven run`, so the new subsection
  there needs a different heading text.
- **Ordering.** Keep each list in its current order and append new keys, rather than re-sorting.
  A re-sorted list makes the diff unreadable for no benefit.

## Risks

| Risk | Mitigation |
| ---- | ---------- |
| The lists are synced against `PRD.md`'s table instead of the code, and are wrong again if merge order differs | REQ-1 and REQ-2 are stated against `resolve_config`, and the Phase 1 and Phase 2 verification steps both re-derive the set from `src/prinfo/config.py` before comparing |
| `PRINFO_*` names inside the `--skip-check-logs` error message are counted as resolver keys | Called out in Implementation Notes; the verification step reads the `env_values.get` lines specifically |
| The new subsection contradicts `_resolve_env_file` on precedence | Every clause of REQ-3 maps to a line in `src/prinfo/config.py:92-102`; the phase verification re-reads that function |
| A doc-only change silently touches source | AC-6 asserts `git diff` touches nothing under `src/` or `tests/` |
| The same drift recurs on the next added key | Accepted for this task. The guard test was declined in Q3 and is recorded under `## Non-Requirements` for a follow-up |

## Test Strategy

| Level | File | What it covers |
| ----- | ---- | -------------- |
| Gate - Markdown | -- | `markdownlint-cli2 "**/*.md" "#node_modules"` clean across both changed files (AC-5) |
| Gate - regression | -- | `uv run pytest` and `uv run ruff check .` unchanged, proving the change is documentation-only (AC-6) |
| Manual - derived set | `src/prinfo/config.py` | The documented key set is re-derived from the `env_values.get` lookups and compared to each list (AC-1, AC-2) |
| Manual - prose | `src/prinfo/config.py:92-102` | Each clause of the `PRINFO_ENV_FILE` subsection is checked against `_resolve_env_file` (AC-3, AC-4) |

No automated test is added. The project has no documentation test today, and the drift guard that
would provide one was declined in Q3 and recorded as a non-requirement.
