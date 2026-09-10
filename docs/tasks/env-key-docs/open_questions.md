# Open Questions: Document Every PRINFO Env Key

## Q1: How should `PRINFO_ENV_FILE` be presented, given it is not an env-file key?

- **Why it matters**: This is the whole reason the key went undocumented, and it decides whether the
  fix is one bullet or a short explanatory paragraph. `resolve_config` reads every other key from
  `env_values`, which `_load_env_values` builds from the env file through `dotenv_values`
  (`src/prinfo/config.py:37`). `PRINFO_ENV_FILE` is different: `_resolve_env_file` reads it from
  `env_source`, the **process environment** (`src/prinfo/config.py:93`). It selects which env file to
  load, so by construction it cannot be set inside that file. Dropping it into a list headed
  "Supported env keys" would make a reader put it in their env file, where it does nothing.
- **Options**: (a) append it to the existing list with no qualifier; (b) document it separately, in
  its own short subsection, stating that it is read from the process environment and names the env
  file the other keys come from; (c) keep it in the list but with an inline parenthetical.
- **Recommended**: (b) - the two mechanisms are genuinely different, and the list's own title is what
  misleads. A separate subsection can also say the thing a user actually needs to know, which is that
  `--env-file` and `PRINFO_ENV_FILE` are the two ways to point at a file.
- **Answer**: (b) - decided by user. `PRINFO_ENV_FILE` gets its own subsection in both documents,
  stating that it is read from the process environment, that it names the env file the other keys are
  read from, that it cannot be set inside that file, and that it is the equivalent of `--env-file`.

## Q2: Should the other keys be documented as env-file only?

- **Why it matters**: Related to Q1 and cheap to get wrong. `PRINFO_PR`, `PRINFO_REPO` and the rest
  are read only from `env_values`, never from `os.environ`. A user who exports `PRINFO_PR=5` in their
  shell and runs `prinfo` gets nothing, with no error explaining why. The current docs never say the
  keys come from a file rather than the environment, and the phrase "env keys" invites the wrong
  reading.
- **Options**: (a) leave the wording as is and only add the missing keys; (b) add one sentence saying
  these keys are read from the env file and not from the shell environment.
- **Recommended**: (b) - it is one sentence, it is squarely part of describing the inputs correctly,
  and it prevents the same misreading that hid `PRINFO_ENV_FILE`.
- **Answer**: (b) - decided by user. One sentence in each document saying the listed keys are read
  from the env file and not from exported shell variables.

## Q3: Should a test guard the docs against drifting again?

- **Why it matters**: These gaps appeared because a key was added to `config.py` and the two lists
  were updated by hand, one of them incompletely. Nothing fails when they disagree, so the same
  drift will recur. A test can read the `PRINFO_*` keys out of `src/prinfo/config.py` and assert each
  appears in `README.md` and `skills/prinfo/references/commands.md`.
- **Options**: (a) documentation-only change, no test; (b) add a drift test in `tests/`; (c) add the
  test but mark it non-blocking.
- **Recommended**: (b) - it is a small test over files already in the repo, it needs no network and
  no fixture, and it converts a silent documentation bug into a failing gate. It also has to encode
  the Q1 answer, since `PRINFO_ENV_FILE` lives in a different section.
- **Answer**: (a) - decided by user. No drift test is added; this task stays documentation-only. The
  guard is recorded under `## Non-Requirements` in `PRD.md` so it is not lost.

## Q4: Should `skills/prinfo/references/commands.md` keep its own list at all?

- **Why it matters**: Two hand-maintained lists is what produced the disagreement. The skill file
  could point at `README.md` instead of repeating the keys.
- **Options**: (a) keep both lists and sync them; (b) have the skill reference point at `README.md`.
- **Recommended**: (a) - the skill is loaded on its own by an agent that may never read `README.md`,
  so a self-contained list is worth the duplication, provided Q3 adds the guard that keeps them
  honest.
- **Answer**: (a) - decided by user. Both documents keep their own list, because the skill is loaded
  standalone by an agent that may never read `README.md`.

## Resolution Summary

| ID | Status | Carried by |
| -- | ------ | ---------- |
| Q1 | Answered | REQ-3 |
| Q2 | Answered | REQ-4 |
| Q3 | Answered | `## Non-Requirements` in PRD.md |
| Q4 | Answered | REQ-2 |
