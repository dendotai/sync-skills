---
name: sync-skills
description: Manage forks of upstream Claude skills — install from GitHub, fetch updates, review and merge changes hunk-by-hunk while preserving your customizations.
---

# sync-skills

Maintain a personal fork of an upstream Claude skill. State lives under `~/.agents/sync-skills/<name>/` in three sibling trees (`active/` / `baseline/` / `upstream/`); `~/.claude/skills/<name>` is a symlink into `active/`.

## Bundled scripts

Run with `python3` (stdlib only). From within the skill folder:

- `python3 scripts/install.py <name> <owner/repo> <path> [ref]` — register a skill, seed all three trees from upstream, and create the symlink.
- `python3 scripts/list.py` — show all registered skills.
- `python3 scripts/paths.py <name>` — print the active / baseline / upstream / symlink paths for a skill.

More subcommands (`fetch`, `diff`, `accept`, `migrate`, `remove`, `relink-all`, `doctor`) and the interactive `/sync-skills` review flow land in follow-up issues.
