# Install `prinfo` Skill

## Contents

- [Source](#source)
- [Claude Code](#claude-code)
- [VS Code](#vs-code)
- [Cursor](#cursor)
- [Codex App](#codex-app)
- [References](#references)

## Source

Install the skill from:

```text
skills/prinfo/
```

`docs/tasks/skill/` is reserved for task notes and supporting documentation.

## Claude Code

Project-local install:

```bash
mkdir -p .claude/skills/prinfo
cp -R skills/prinfo/. .claude/skills/prinfo
```

Optional user-level install:

```bash
mkdir -p ~/.claude/skills/prinfo
cp -R skills/prinfo/. ~/.claude/skills/prinfo
```

Verify in Claude Code:

```text
/prinfo
```

## VS Code

VS Code supports Agent Skills directly.

Project-local install:

```bash
mkdir -p .github/skills/prinfo
cp -R skills/prinfo/. .github/skills/prinfo
```

Optional user-level install:

```bash
mkdir -p ~/.copilot/skills/prinfo
cp -R skills/prinfo/. ~/.copilot/skills/prinfo
```

Verify in VS Code Chat:

```text
Use prinfo to troubleshoot skipped checks in manifest.json.
```

VS Code also supports `.agents/skills`, `~/.agents/skills`, `.claude/skills`,
and `~/.claude/skills`.

## Cursor

Cursor supports Agent Skills directly.

Project-local install:

```bash
mkdir -p .cursor/skills/prinfo
cp -R skills/prinfo/. .cursor/skills/prinfo
```

Optional user-level install:

```bash
mkdir -p ~/.cursor/skills/prinfo
cp -R skills/prinfo/. ~/.cursor/skills/prinfo
```

Verify in Cursor:

```text
/prinfo
```

Cursor also auto-discovers compatible skills from `.claude/skills`,
`~/.claude/skills`, `.codex/skills`, and `~/.codex/skills`.

## Codex App

Codex app loads skills from `$CODEX_HOME/skills` or `~/.codex/skills`.

Install:

```bash
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME_DIR/skills/prinfo"
cp -R skills/prinfo/. "$CODEX_HOME_DIR/skills/prinfo"
```

Verify in Codex:

```text
Use the prinfo skill to build the command for PR 123.
```

## References

- [Anthropic: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [VS Code: Use agent skills](https://code.visualstudio.com/docs/copilot/chat/chat-agent-skills)
- [VS Code: Agent plugins in VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-plugins)
- [Cursor: Agent Skills](https://cursor.com/docs/skills)
