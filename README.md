# sync-skills

A Claude Code skill (and bundled CLI) for managing other Claude skills you've installed from GitHub: keep a baseline of the upstream version your fork was based on, fetch updates without overwriting your customizations, and review upstream changes hunk by hunk.

## Status

Four scripts: `install`, `migrate`, `relink`, `doctor`. Sync returns with #56.

## Install

```bash
bunx skills add dendotai/sync-skills
# or: npx skills add dendotai/sync-skills
```

Reload Claude Code so `/sync-skills` is registered.

## What is in `~/.agents/sync-skills/skills/<name>/`

Each managed skill has one folder. The set of folders is the list of managed skills; nothing else records it.

- `current/` is the copy Claude runs: `~/.claude/skills/<name>` is a symlink to it. Your edits go here. It changes when you edit the skill or accept an upstream change.
- `baseline/` is the upstream folder as of the last review. Sync compares it with the new upstream to find what upstream changed. It changes only when a review finishes.
- `source.json` says where upstream is: `repo`, `path` inside the repo, and `commit`, the upstream commit `baseline/` was taken from. `commit` is `null` when no upstream commit matched at migration. It changes with `baseline/`.
- `history.log` holds one tab-separated line per event on this skill (install, migrate, relink, doctor fix). Lines are only added.

Copy one folder to another machine and run `relink` to get its symlink back.

## Scenarios

### Fresh install

```bash
bunx skills add dendotai/sync-skills
```

Reload Claude Code, then run:

```
/sync-skills
```

The pre-flight detects sync-skills was just installed via `bunx`/`npx skills` (so it's vercel-managed) and offers to migrate it. Pick `migrate-all`.

If you already have other skills installed via `bunx`/`npx skills add`, they appear in the same migration prompt.

### Migrating existing `npx skills` installs

If you've installed skills via `bunx`/`npx skills add` previously, they live in `~/.agents/.skill-lock.json`. After installing sync-skills, run:

```
/sync-skills
```

The pre-flight lists every locked skill and offers `migrate-all` / `migrate-some` / `skip`. Each migration:

- copies `~/.agents/skills/<name>/` into `current/`
- clones the upstream and takes `baseline/` from the newest commit whose skill folder matches the one the installer recorded; with no match, `baseline/` is a copy of your local folder
- swings the `~/.claude/skills/<name>` symlink into `current/`
- drops the entry from `.skill-lock.json`

Or migrate one at a time from the shell:

```bash
python3 ~/.claude/skills/sync-skills/scripts/migrate.py grill-me
```

### Sync

Sync returns with #56.
