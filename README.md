# sync-skills

A Claude Code skill (and bundled CLI) for managing other Claude skills you've installed from GitHub: keep a baseline of the upstream version your fork was based on, fetch updates without overwriting your customizations, and review/merge upstream changes hunk-by-hunk.

## Status

Early. Spec lives in the GitHub issue tagged `prd`.

## Install

```
npx skills add dendotai/sync-skills
```

(Once published — currently bootstrapping.)

## Usage

In Claude Code:

```
/sync-skills
```

Walks you through any upstream changes for skills you've forked.
