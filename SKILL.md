---
name: sync-skills
description: Manage forks of upstream Claude skills — install from GitHub, fetch updates, review and merge changes hunk-by-hunk while preserving your customizations.
---

# sync-skills

Maintain a personal fork of an upstream Claude skill. Each managed skill lives in `~/.agents/sync-skills/skills/<name>/`: `current/` (the copy Claude runs; `~/.claude/skills/<name>` is a symlink to it), `baseline/` (upstream as of the last review), `source.json` (`repo`, `path`, `commit`), and `history.log`. What each one is for: the README section "What is in `~/.agents/sync-skills/skills/<name>/`".

## Bundled scripts

Self-contained Python 3, stdlib only. Run directly:

```bash
python3 ~/.claude/skills/sync-skills/scripts/install.py <name> <owner/repo> <path> [ref]
python3 ~/.claude/skills/sync-skills/scripts/migrate.py [name]
python3 ~/.claude/skills/sync-skills/scripts/relink.py
python3 ~/.claude/skills/sync-skills/scripts/doctor.py [--yes]
```

`install` fetches a skill, seeds `current/` and `baseline/`, writes `source.json` with the fetched commit, creates the symlink, and starts `history.log`. `migrate` ports a skill installed via `npx skills` (vercel-labs/skills): copies `~/.agents/skills/<name>/` into `current/`, takes `baseline/` from the newest upstream commit whose folder matches the lock entry's `skillFolderHash` (with no match, from the local folder, and `commit` is `null`), swings the symlink, and removes the entry from `~/.agents/.skill-lock.json`. With no name, migrates every entry in the lock file. `relink` recreates every `~/.claude/skills/<name>` symlink from the folders under `skills/` — the cross-machine restore. Idempotent; refuses to overwrite a non-symlink at the target path. `doctor` scans for drift (broken symlink, vercel clobber plus stranded edits, double-managed lock entry, missing `current/` or `baseline/`) and prints findings; pass `--yes` to apply every fix it has. A missing `baseline/` is refetched at the recorded commit; a missing `current/` has no fix. Each applied fix appends a `doctor-fix` line to the skill's `history.log`.

> **Clobber risk.** `npx skills` rewrites `~/.claude/skills/<name>` to point into `~/.agents/skills/<name>`, silently breaking the symlink into `current/`. The `/sync-skills` pre-flight catches this; `doctor` is the standalone equivalent.

`sync_skills.py` (sibling to the four standalone scripts) is the inline-helper dispatcher used by `/sync-skills`; its subcommands stand in for what would otherwise be inline-Python blocks in this file.

> **Allowlist.** A single entry — `Bash(python3 ~/.claude/skills/sync-skills/scripts/*.py *)` — covers the dispatcher and all four standalone scripts, silencing future `/sync-skills` permission prompts.

## Inspecting state

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py list   # managed skills
cat ~/.agents/sync-skills/skills/<name>/source.json | jq            # where upstream is
tail ~/.agents/sync-skills/skills/<name>/history.log                # events
```

## /sync-skills

When the user invokes `/sync-skills`, run the pre-flight below. Sync returns with #56; until then, tell the user after the pre-flight that sync is not available yet.

### Pre-flight

Surface drift before anything else runs.

**a. First-run hint.** If both `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py list` and `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py migration-candidates` print nothing, print:

> No skills managed yet. Install one with `python3 ~/.claude/skills/sync-skills/scripts/install.py <name> <owner/repo> <path>`.

…and stop.

**b. Migration prompt.** If `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py migration-candidates` is non-empty, list them and `AskUserQuestion`: `migrate-all` / `migrate-some` / `skip`. On `migrate-all`, run `migrate.py` with no args. On `migrate-some`, ask per-skill, then call `migrate.py <name>` for each chosen.

**c. Clobber check + stranded-edit handling.** Get the list of clobbered managed skills:

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py clobbered-list
```

For each `name` in that list:

1. If `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py stranded-edit <name>` exits 0, `AskUserQuestion`: `import-then-relink` / `relink-only` / `defer`.
   - `import-then-relink` — `cp ~/.agents/skills/<name>/SKILL.md ~/.agents/sync-skills/skills/<name>/current/SKILL.md`, then re-link.
   - `relink-only` — re-link, drop the npx-side edit.
   - `defer` — leave it; this skill is excluded from the rest of this run.
2. Otherwise `AskUserQuestion`: `relink` / `defer`.
3. Re-link by running `python3 ~/.claude/skills/sync-skills/scripts/relink.py` once after the loop (idempotent across all skills).
