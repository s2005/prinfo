# Progress: Document Every PRINFO Env Key

## Status Legend

| Marker | Meaning |
| ------ | ------- |
| `[ ]` | Not started |
| `[x]` | Complete |
| `[~]` | In progress |
| `[!]` | Blocked or needs decision |
| `[-]` | Skipped / not applicable |

## Planning Checklist

- [x] Analyze current behavior.
- [x] Create open_questions.md and resolve every entry
- [x] Create analysis.md
- [x] Create PRD.md
- [x] Create implementation_plan.md
- [x] Create verification.md
- [x] Create progress.md

## Phase 1: README env key reference

Requirements: REQ-1, REQ-3, REQ-4

- [x] Derive the key set from the `env_values.get` lookups in `src/prinfo/config.py`, ignoring the `PRINFO_*` names inside the `--skip-check-logs` error message.
- [-] Add every missing key to the supported-env-keys list in `README.md`, appended in resolver order.
- [-] Remove any listed key the resolver does not read.
- [x] Retitle the list lead-in so it names the env file as the source.
- [x] Add the sentence saying the listed keys are not read from exported shell variables.
- [x] Add the `PRINFO_ENV_FILE` subsection covering process-environment origin, the `--env-file` precedence and the `.env` fallback.
- [x] Check every clause of that subsection against `_resolve_env_file` in `src/prinfo/config.py`.
- [x] Confirm the new heading text is unique within `README.md`.
- [x] Run `markdownlint-cli2 "**/*.md" "#node_modules"`.
- [x] Run the derived-set comparison for `README.md` and confirm both differences are empty.

The `README.md` list already held all eleven keys in resolver order, so the two
list-repair steps had nothing to change; the derived-set comparison confirms it.

## Phase 2: Skill command reference

Requirements: REQ-2, REQ-3, REQ-4

- [x] Bring the supported-keys list in `skills/prinfo/references/commands.md` to the set derived in Phase 1.
- [x] Keep the list in this file rather than pointing at `README.md`.
- [x] Keep the `--skip-empty-logs` sentence.
- [x] Keep the sentence about CLI flags overriding env-file values.
- [x] Add the env-file-origin sentence, reusing the Phase 1 wording.
- [x] Add the `PRINFO_ENV_FILE` coverage, reusing the Phase 1 wording.
- [x] Confirm the new heading text does not collide with `## Environment file driven run`.
- [x] Run `markdownlint-cli2 "**/*.md" "#node_modules"`.
- [x] Run the derived-set comparison for `commands.md` and confirm it is empty.
- [x] Run `uv run pytest` and `uv run ruff check .` and confirm `git diff` touches no file under `src/` or `tests/`.

The new heading is nested as a level-3 heading under `## Environment file driven run`
rather than added as a level-2 sibling: every level-2 heading in that file is a
runnable recipe, and the new content is prose qualifying the list above it. This
also mirrors the `README.md` structure from Phase 1.

## Review Feedback

(Section appears when PR review feedback arrives. Each comment gets a checkbox.)
