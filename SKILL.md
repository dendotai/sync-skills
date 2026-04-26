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
python3 ~/.claude/skills/sync-skills/scripts/migrate.py [name]
python3 ~/.claude/skills/sync-skills/scripts/relink.py
```

`install` registers a skill, seeds all three trees from upstream, creates the symlink, and appends an audit event. `accept` advances the baseline (`baseline := upstream`) — the primitive behind cherry-pick, wholesale, and skip in `/sync-skills`. `migrate` ports a skill installed via `npx skills` (vercel-labs/skills) into sync-skills: copies `~/.agents/skills/<name>/` into all three trees, swings the symlink, registers it, and removes the entry from `~/.agents/.skill-lock.json`. With no name, migrates every entry in the lock file. `relink` recreates every `~/.claude/skills/<name>` symlink from `sources.json` — the cross-machine restore: drop a saved `~/.agents/sync-skills/` folder onto a fresh machine, run `relink`, all symlinks come back. Idempotent; refuses to overwrite a non-symlink at the target path.

More scripts (`doctor`) and the interactive `/sync-skills` review flow land in follow-up issues. Trivial operations (list, fetch, diff, remove) are inline `Bash` calls in this file once the review flow lands.

## Inspecting state

Until `/sync-skills` lands, you can inspect things directly:

```bash
cat ~/.agents/sync-skills/sources.json | jq               # registered skills
ls ~/.agents/sync-skills/<name>/                          # the three trees
tail ~/.agents/sync-skills/history.log                    # audit
```
