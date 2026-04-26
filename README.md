# sync-skills

A Claude Code skill (and bundled CLI) for managing other Claude skills you've installed from GitHub: keep a baseline of the upstream version your fork was based on, fetch updates without overwriting your customizations, and review/merge upstream changes hunk-by-hunk.

## Status

v1 shipped. Five scripts (`install`, `accept`, `migrate`, `relink`, `doctor`) + the `/sync-skills` interactive review flow. See issue #1 for the spec.

## Install

```bash
bunx skills add dendotai/sync-skills
# or: npx skills add dendotai/sync-skills
```

Reload Claude Code so `/sync-skills` is registered.

## Scenarios

### Fresh install

```bash
bunx skills add dendotai/sync-skills
```

Reload Claude Code, then run:

```
/sync-skills
```

The pre-flight detects sync-skills was just installed via `bunx`/`npx skills` (so it's vercel-managed) and offers to migrate it into self-managed state. Pick `migrate-all`.

After migration, `~/.claude/skills/sync-skills` symlinks into `~/.agents/sync-skills/sync-skills/active/` (sync-skills's own three-tree state model), and `/sync-skills` can update itself the next time you push a commit to upstream.

If you already have other skills installed via `bunx`/`npx skills add`, they appear in the same migration prompt.

### Migrating existing `npx skills` installs

If you've installed skills via `bunx`/`npx skills add` previously, they live in `~/.agents/.skill-lock.json`. After installing sync-skills, run:

```
/sync-skills
```

The pre-flight lists every locked skill and offers `migrate-all` / `migrate-some` / `skip`. Each migration:

- copies `~/.agents/skills/<name>/` into `~/.agents/sync-skills/<name>/{active,baseline,upstream}/`
- swings the `~/.claude/skills/<name>` symlink into `active/`
- drops the entry from `.skill-lock.json`

Or migrate one at a time from the shell:

```bash
python3 ~/.claude/skills/sync-skills/scripts/migrate.py grill-me
```

### Self-update loop

You've customised a skill in `active/` and now upstream has new commits you want to consider:

1. `/sync-skills` runs the pre-flight, then fetches every registered upstream.
2. For each skill where `baseline/` differs from `upstream/`, you're offered four options:
   - **cherry-pick** — walk the diff hunk-by-hunk; pick what to merge.
   - **wholesale** — replace `active/` with `upstream/`; take everything.
   - **skip** — keep your version; advance the baseline so this change isn't shown again.
   - **defer** — leave the baseline; revisit next sync.
3. Each outcome lands in `~/.agents/sync-skills/history.log`.

If `Edit` fails because your customisation overlaps upstream's same lines, you'll be offered `edit-manually` / `skip-hunk` / `wholesale-this-skill`.
