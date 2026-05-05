---
name: skill-creator
description: >
  Creates new AI agent skills for the octotrace project following the Agent Skills spec.
  Trigger: When asked to create a new skill, document a reusable pattern, or add agent instructions.
license: MIT
metadata:
  author: nahuel
  version: "1.0"
  scope: [root]
  auto_invoke: "Creating new skills"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

## When to Use

Use this skill when:
- A pattern is used repeatedly and the AI needs guidance
- octotrace-specific conventions differ from generic best practices
- Complex workflows need step-by-step instructions
- Decision trees help the AI choose the right approach

**Don't create a skill when:**
- The pattern is trivial or self-explanatory
- It's a one-off task
- Documentation already exists elsewhere (reference instead)

---

## Critical Patterns

### Pattern 1: Skill location
All skills live under `skills/{skill-name}/SKILL.md` in the project root.

### Pattern 2: Always register after creating
After creating a skill, add it to `AGENTS.md` in the Available Skills table.

### Pattern 3: Frontmatter is mandatory
Every SKILL.md must have complete frontmatter — name, description with Trigger, license, metadata.

---

## Decision Tree

~~~
Pattern applies to ANY project?       → Generic skill (e.g., python, db)
Pattern is octotrace-specific?        → octotrace-{name} skill
Need code templates or schemas?       → Add assets/
Need links to local docs?             → Add references/ (local paths only, no web URLs)
Skill already exists in skills/?      → Update it, don't duplicate
~~~

---

## Naming Conventions

| Type | Pattern | Examples |
|------|---------|----------|
| Generic | `{technology}` | `python`, `db`, `trace` |
| octotrace-specific | `octotrace-{component}` | `octotrace-crawler`, `octotrace-export` |
| API reference | `{provider}` | `etherscan`, `tronscan` |
| Workflow | `{action}-{target}` | `skill-creator`, `git-commits` |

---

## Skill Structure

~~~
skills/{skill-name}/
├── SKILL.md              # Required
├── assets/               # Optional — templates, schemas, examples
│   └── SKILL-TEMPLATE.md
└── references/           # Optional — links to local docs
    └── docs.md
~~~

---

## Commands

~~~bash
mkdir -p skills/{skill-name}/assets
cp skills/skill-creator/assets/SKILL-TEMPLATE.md skills/{skill-name}/SKILL.md
~~~

---

## Checklist Before Creating

- [ ] Skill doesn't already exist in `skills/`
- [ ] Pattern is reusable, not one-off
- [ ] Name follows conventions above
- [ ] Frontmatter is complete (description includes Trigger keywords)
- [ ] Critical patterns are clear and minimal
- [ ] Code examples are focused
- [ ] Commands section exists
- [ ] Added to `AGENTS.md`

---

## Resources

- **Template**: See [assets/SKILL-TEMPLATE.md](assets/SKILL-TEMPLATE.md) for the base template