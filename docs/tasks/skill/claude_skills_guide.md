# The Complete Guide to Building Skills for Claude

## Contents

- [Introduction](#introduction)
- [Chapter 1: Fundamentals](#chapter-1-fundamentals)
- [Chapter 2: Planning and Design](#chapter-2-planning-and-design)
- [Chapter 3: Testing and Iteration](#chapter-3-testing-and-iteration)
- [Chapter 4: Distribution and Sharing](#chapter-4-distribution-and-sharing)
- [Chapter 5: Patterns and Troubleshooting](#chapter-5-patterns-and-troubleshooting)
- [Chapter 6: Resources and References](#chapter-6-resources-and-references)
- [Reference A: Quick Checklist](#reference-a-quick-checklist)
- [Reference B: YAML Frontmatter](#reference-b-yaml-frontmatter)

---

## Introduction

A skill is a set of instructions - packaged as a simple folder - that teaches Claude how to handle specific tasks or workflows. Skills are one of the most powerful ways to customize Claude for your specific needs. Instead of re-explaining your preferences, processes, and domain expertise in every conversation, skills let you teach Claude once and benefit every time.

Skills are powerful when you have repeatable workflows: generating frontend designs from specs, conducting research with consistent methodology, creating documents that follow your team's style guide, or orchestrating multi-step processes. They work well with Claude's built-in capabilities like code execution and document creation. For those building MCP integrations, skills add another powerful layer helping turn raw tool access into reliable, optimized workflows.

This guide covers everything you need to know to build effective skills - from planning and structure to testing and distribution.

---

## Chapter 1: Fundamentals

### What is a skill?

A skill is a folder containing:

- **SKILL.md (required)**: Instructions in Markdown with YAML frontmatter.
- **scripts/ (optional)**: Executable code (Python, Bash, etc.).
- **references/ (optional)**: Documentation loaded as needed.
- **assets/ (optional)**: Templates, fonts, icons used in output.

### Core Design Principles

#### Progressive Disclosure

Skills use a three-level system:

1. **First level (YAML frontmatter)**: Always loaded in Claude's system prompt. Provides just enough information for Claude to know when each skill should be used.
2. **Second level (SKILL.md body)**: Loaded when Claude thinks the skill is relevant to the current task. Contains the full instructions.
3. **Third level (Linked files)**: Additional files bundled within the skill directory that Claude can choose to navigate as needed.

#### Composability

Claude can load multiple skills simultaneously. Your skill should work well alongside others.

#### Portability

Skills work identically across Claude.ai, Claude Code, and API.

### For MCP Builders: Skills + Connectors

MCP provides the professional kitchen (tools, ingredients). Skills provide the recipes (step-by-step instructions on how to create something valuable).

---

## Chapter 2: Planning and Design

### Use Case Definition

Identify 2-3 concrete use cases.
Example: **Project Sprint Planning**

- **Trigger**: "help me plan this sprint"
- **Steps**: Fetch status from Linear, analyze velocity, suggest prioritization, create tasks.

### Technical Requirements

#### File Structure

```text
your-skill-name/
├── SKILL.md              # Required - main skill file
├── scripts/              # Optional - executable code
├── references/           # Optional - documentation
└── assets/              # Optional - templates, etc.
```

#### Critical Rules

- **SKILL.md**: Must be exactly `SKILL.md` (case-sensitive).
- **Folder naming**: Use `kebab-case`.
- **No README.md**: Inside the skill folder, all docs go in `SKILL.md` or `references/`.

#### YAML Frontmatter

The YAML frontmatter is how Claude decides whether to load your skill.

```yaml
---
name: your-skill-name
description: What it does. Use when user asks to [specific phrases].
---
```

- **name**: kebab-case, matches folder name.
- **description**: MUST include what it does and trigger conditions (under 1024 chars).

### Writing Effective Instructions

- Be specific and actionable.
- Include error handling.
- Reference bundled resources clearly.
- Use progressive disclosure (keep SKILL.md focused, move details to `references/`).

---

## Chapter 3: Testing and Iteration

### Testing Levels

- **Manual**: In Claude.ai.
- **Scripted**: In Claude Code.
- **Programmatic**: Via skills API.

### Recommended Testing Areas

1. **Triggering tests**: Does it load when it should? (Obvious tasks, paraphrased requests, negative cases).
2. **Functional tests**: Correct outputs, API success, error handling.
3. **Performance comparison**: Results vs. baseline (tokens, tool calls, user corrections).

---

## Chapter 4: Distribution and Sharing

### Distribution Model

- **Claude.ai**: Upload folder as ZIP via Settings > Capabilities > Skills.
- **Claude Code**: Place in `skills/` directory.
- **Organization**: Admins can deploy workspace-wide.

### Using Skills via API

Key capabilities: `/v1/skills` endpoint, `container.skills` parameter in Messages API. Requires Code Execution Tool beta.

---

## Chapter 5: Patterns and Troubleshooting

### Common Patterns

1. **Sequential workflow orchestration**: Multi-step processes in specific order.
2. **Multi-MCP coordination**: Workflows spanning multiple services (e.g., Figma -> Drive -> Linear).
3. **Iterative refinement**: Output quality improves with validation loops.
4. **Context-aware tool selection**: Same outcome, different tools depending on file type/size.
5. **Domain-specific intelligence**: Specialized knowledge (e.g., financial compliance checks).

### Troubleshooting

- **Skill won't upload**: Check file naming (`SKILL.md`) and YAML formatting.
- **Doesn't trigger**: Revise the description field to include better trigger phrases.
- **Triggers too often**: Add negative triggers or be more specific.
- **Instructions not followed**: Keep them concise, use headers like `## Critical`, and address model "laziness".

---

## Chapter 6: Resources and References

- **Public Repo**: `github.com/anthropics/skills`
- **skill-creator**: Built-in skill to help design and refine skills.

---

## Reference A: Quick Checklist

- [ ] Folder named in kebab-case.
- [ ] `SKILL.md` exists exactly as named.
- [ ] YAML frontmatter has `---` delimiters.
- [ ] Description includes WHAT and WHEN.
- [ ] Instructions are actionable.
- [ ] Error handling included.

---

## Reference B: YAML Frontmatter

```yaml
---
name: skill-name
description: [required description]
license: MIT
metadata:
  author: Company Name
  version: 1.0.0
  mcp-server: server-name
---
```

- Forbidden: XML angle brackets (`< >`), names starting with "claude" or "anthropic".
