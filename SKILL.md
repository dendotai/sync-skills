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
python3 ~/.claude/skills/sync-skills/scripts/doctor.py [--yes]
```

`install` registers a skill, seeds all three trees from upstream, creates the symlink, and appends an audit event. `accept` advances the baseline (`baseline := upstream`) — the primitive behind cherry-pick, wholesale, and skip in `/sync-skills`. `migrate` ports a skill installed via `npx skills` (vercel-labs/skills) into sync-skills: copies `~/.agents/skills/<name>/` into all three trees, swings the symlink, registers it, and removes the entry from `~/.agents/.skill-lock.json`. With no name, migrates every entry in the lock file. `relink` recreates every `~/.claude/skills/<name>` symlink from `sources.json` — the cross-machine restore: drop a saved `~/.agents/sync-skills/` folder onto a fresh machine, run `relink`, all symlinks come back. Idempotent; refuses to overwrite a non-symlink at the target path. `doctor` scans for the six known state-drift failure modes (broken symlink, vercel clobber + stranded edits, registry orphan, folder orphan, double-managed lock entry, missing layer) and prints findings; pass `--yes` to apply every proposed fix. Each applied fix appends a `doctor-fix` audit event.

> **Clobber risk.** `npx skills` rewrites `~/.claude/skills/<name>` to point into `~/.agents/skills/<name>`, silently breaking the symlink into `active/`. The `/sync-skills` pre-flight catches this; `doctor` is the standalone equivalent.

`sync_skills.py` (sibling to the five standalone scripts) is the inline-helper dispatcher used by `/sync-skills`; its subcommands stand in for what would otherwise be inline-Python blocks in this file.

> **Allowlist.** A single entry — `Bash(python3 ~/.claude/skills/sync-skills/scripts/*.py *)` — covers the dispatcher and all five standalone scripts, silencing future `/sync-skills` permission prompts.

## Inspecting state

```bash
cat ~/.agents/sync-skills/sources.json | jq               # registered skills
ls ~/.agents/sync-skills/<name>/                          # the three trees
tail ~/.agents/sync-skills/history.log                    # audit
```

## /sync-skills

The interactive review flow. When the user invokes `/sync-skills`, walk these steps in order. Throughout, prefer the bundled `sync_skills.py` dispatcher subcommands over hand-rolled `git`/`diff` so behaviour matches what the scripts do.

### 0. Pre-flight (run before fetching)

Surface drift before the user reviews changes against a broken setup.

**a. First-run hint.** If both `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py registry-list` returns `{}` AND `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py migration-candidates` is empty, print:

> No skills registered yet. Install one with `python3 ~/.claude/skills/sync-skills/scripts/install.py <name> <owner/repo> <path>`.

…and stop.

**b. Migration prompt.** If `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py migration-candidates` is non-empty, list them and `AskUserQuestion`: `migrate-all` / `migrate-some` / `skip`. On `migrate-all`, run `migrate.py` with no args. On `migrate-some`, ask per-skill, then call `migrate.py <name>` for each chosen.

**c. Clobber check + stranded-edit handling.** Get the list of clobbered registered skills:

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py clobbered-list
```

For each `name` in that list:

1. If `python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py stranded-edit <name>` exits 0, `AskUserQuestion`: `import-then-relink` / `relink-only` / `defer`.
   - `import-then-relink` — `cp ~/.agents/skills/<name>/SKILL.md ~/.agents/sync-skills/<name>/active/SKILL.md`, then re-link.
   - `relink-only` — re-link, drop the npx-side edit.
   - `defer` — leave it; this skill is excluded from the rest of this run.
2. Otherwise `AskUserQuestion`: `relink` / `defer`.
3. Re-link by running `python3 ~/.claude/skills/sync-skills/scripts/relink.py` once after the loop (idempotent across all skills).

### 1. Fetch every registered upstream

For each entry in `sources.json`, clone its `repo` at `ref` and refresh `<sync_root>/<name>/upstream/`:

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py fetch-all
```

### 2. Identify `upstream-changed` skills

A skill is `upstream-changed` when `baseline/` and `upstream/` differ:

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py changed-list
```

### 3. If nothing changed

Tell the user "All skills are up to date." and stop.

### 4. Per-skill loop

For each `upstream-changed` skill, in registry order:

**a. One-line summary.** Run `diff -urq ~/.agents/sync-skills/<name>/baseline ~/.agents/sync-skills/<name>/upstream` to list changed files, then describe the gist in one sentence.

**b. Ask `AskUserQuestion`** with four options:

- `cherry-pick` — walk the diff hunk-by-hunk, pick what to merge.
- `wholesale` — replace `active/` with `upstream/`.
- `skip` — keep mine, advance baseline so we stop nagging.
- `defer` — leave it `upstream-changed`, decide later.

**c. Execute the chosen path** (each path emits its named audit event; cherry-pick / wholesale / skip additionally call `accept` which emits its own).

#### cherry-pick

1. Capture the diff and parse it into hunks in one shot:
   ```bash
   diff -ur ~/.agents/sync-skills/<name>/baseline ~/.agents/sync-skills/<name>/upstream | python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py parse-hunks
   ```
   Output is a JSON list of `{file, old_string, new_string}` objects. `file` is the path relative to the skill root.
2. For each hunk, `AskUserQuestion`: `include` / `exclude`. Show a short preview of `old_string` → `new_string`.
3. Before the first `Edit` in this round, snapshot `active/SKILL.md`:
   ```bash
   python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py backup-active <name>
   ```
   (One backup per skill per round is enough; the helper overwrites any prior `.bak`.)
4. Apply each included hunk via `Edit` against `~/.agents/sync-skills/<name>/active/<file>`, passing the hunk's `old_string` / `new_string` verbatim.
5. Append the audit event and advance the baseline:
   ```bash
   python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py audit cherry-pick <name>
   python3 ~/.claude/skills/sync-skills/scripts/accept.py <name>
   ```
6. **Conflict path** — if `Edit` fails because `old_string` no longer matches (the user already customised those lines), surface the failing hunk and `AskUserQuestion`:
   - `edit-manually` — print the hunk and the absolute file path, pause until the user says they merged it.
   - `skip-hunk` — drop just this hunk, continue with the rest.
   - `wholesale-this-skill` — abandon cherry-pick, fall through to the wholesale path below.

#### wholesale

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py wholesale <name>
python3 ~/.claude/skills/sync-skills/scripts/accept.py <name>
```

#### skip

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py audit skip <name>
python3 ~/.claude/skills/sync-skills/scripts/accept.py <name>
```

#### defer

```bash
python3 ~/.claude/skills/sync-skills/scripts/sync_skills.py audit defer <name>
```

### 5. Final summary

Print counts of `synced` (cherry-pick + wholesale), `customized` (cherry-pick rounds that excluded at least one hunk), and `deferred`. Point at `~/.agents/sync-skills/history.log` for the per-skill audit trail.
