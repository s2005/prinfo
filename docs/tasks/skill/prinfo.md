# prinfo Skill Plan

This directory keeps the task notes and design rationale for the `prinfo`
skill.

The actual skill now lives at `skills/prinfo`.

The implementation follows two sources:

- `docs/tasks/skill/claude_skills_guide.md` as the general skill design guide
- [`s2005/cli-helper-skill`](https://github.com/s2005/cli-helper-skill) as a
  concrete example of a compact skill with focused frontmatter and progressive
  disclosure through `references/`

## Concrete use cases

The skill is scoped to the workflows that already exist in this repository:

1. Run `prinfo` against a pull request and export GitHub Actions job logs.
2. Choose the correct authentication mode for `gh` without changing the user's
   global login state.
3. Explain why checks were skipped or why no logs were exported.
4. Interpret `manifest.json` and the generated log file names.

## Design choices

- Keep `SKILL.md` short and procedural.
- Move command recipes and troubleshooting into `references/`.
- Reflect the current CLI exactly:
  `--pr`, `--repo`, `--output-dir`, `--env-file`, `--gh-host`, `--gh-token`,
  `--gh-config-dir`, and `--log-level`.
- Emphasize current product limits:
  only GitHub Actions job logs are exportable and unsupported checks are
  recorded as skipped.

## Repository layout

```text
docs/tasks/skill/
|-- claude_skills_guide.md
`-- prinfo.md

skills/
`-- prinfo/
    |-- SKILL.md
    `-- references/
        |-- commands.md
        |-- outputs.md
        `-- troubleshooting.md
```

## What is implemented now

- Trigger metadata for the `prinfo` skill
- A default workflow for running the CLI
- Command recipes for common invocation patterns
- Output interpretation guidance
- Troubleshooting guidance based on the current Python implementation
- A dedicated `skills/prinfo` location so the skill is separated from task docs

## Notes

- `docs/tasks/skill/` is reserved for the task prompt, guides, and related
  documentation.
- `skills/prinfo/` is the canonical skill package referenced by installation
  instructions.
