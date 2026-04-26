---
name: sync-skills
description: Manage forks of upstream Claude skills — install from GitHub, fetch updates, review and merge changes hunk-by-hunk while preserving your customizations.
---

# sync-skills

Maintain a personal fork of an upstream Claude skill. State lives under `~/.agents/sync-skills/<name>/` in three sibling trees (`active/` / `baseline/` / `upstream/`); `~/.claude/skills/<name>` is a symlink into `active/`.

## Bundled scripts

Self-contained Python 3, stdlib only. Run directly:

```bash
python3 ~/.claude/skills/sync-skills/scripts/install.py <name> <owner/repo> <path> [ref]
python3 ~/.claude/skills/sync-skills/scripts/accept.py <name>
```

`install` registers a skill, seeds all three trees from upstream, creates the symlink, and appends an audit event. `accept` advances the baseline (`baseline := upstream`) — the primitive behind cherry-pick, wholesale, and skip in `/sync-skills`.

More scripts (`migrate`, `relink`, `doctor`) and the interactive `/sync-skills` review flow land in follow-up issues. Trivial operations (list, fetch, diff, remove) are inline `Bash` calls in this file once the review flow lands.

## Inspecting state

Until `/sync-skills` lands, you can inspect things directly:

```bash
cat ~/.agents/sync-skills/sources.json | jq               # registered skills
ls ~/.agents/sync-skills/<name>/                          # the three trees
tail ~/.agents/sync-skills/history.log                    # audit
```
