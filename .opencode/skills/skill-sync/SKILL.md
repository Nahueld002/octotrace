---
name: skill-sync
description: >
  Syncs skill metadata to AGENTS.md Auto-invoke sections.
  Trigger: When updating skill metadata (metadata.scope/metadata.auto_invoke),
  regenerating Auto-invoke tables, or running ./skills/skill-sync/assets/sync.sh.
license: MIT
metadata:
  author: nahuel
  version: "1.0"
  scope: [root]
  auto_invoke:
    - "After creating/modifying a skill"
    - "Regenerate AGENTS.md Auto-invoke tables"
    - "Troubleshoot why a skill is missing from AGENTS.md auto-invoke"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

## Purpose

Keeps AGENTS.md Auto-invoke sections in sync with skill metadata.
When you create or modify a skill, run the sync script to automatically
update all affected AGENTS.md files.

## Required Skill Metadata

Each skill needs these fields in `metadata`:

~~~yaml
metadata:
  author: nahuel
  version: "1.0"
  scope: [root]           # Which AGENTS.md: root, providers, services, web
  auto_invoke: "Action"   # Single string or list (see below)
  # Multiple actions:
  # auto_invoke:
  #   - "Action A"
  #   - "Action B"
~~~

### Scope Values

| Scope | Updates |
|-------|---------|
| `root` | `AGENTS.md` (repo root) |
| `providers` | `src/cryptotrace/providers/AGENTS.md` |
| `services` | `src/cryptotrace/services/AGENTS.md` |
| `web` | `src/cryptotrace/web/AGENTS.md` |

Skills can have multiple scopes: `scope: [root, providers]`

---

## Usage

~~~bash
# Sync all AGENTS.md files
./skills/skill-sync/assets/sync.sh

# Dry run (show what would change)
./skills/skill-sync/assets/sync.sh --dry-run

# Sync specific scope only
./skills/skill-sync/assets/sync.sh --scope providers
~~~

## What It Does

1. Reads all `skills/*/SKILL.md` files
2. Extracts `metadata.scope` and `metadata.auto_invoke`
3. Generates Auto-invoke tables for each AGENTS.md
4. Updates the `### Auto-invoke Skills` section in each file

---

## Checklist After Modifying Skills

- [ ] Added `metadata.scope` to new/modified skill
- [ ] Added `metadata.auto_invoke` with action description
- [ ] Ran `./skills/skill-sync/assets/sync.sh`
- [ ] Verified AGENTS.md files updated correctly
