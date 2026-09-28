"""Port skills installed via `npx skills` (vercel-labs/skills) into sync-skills.

Reads ~/.agents/.skill-lock.json, copies ~/.agents/skills/<name>/ into
current/, takes baseline/ from the upstream commit whose folder matches the
lock entry's hash, writes source.json, replaces the ~/.claude/skills/<name>
symlink with one into current/, and removes the lock entry."""

from __future__ import annotations

import argparse
import sys

import sync_skills as core


def _path_from_skillpath(skill_path: str) -> str:
    if skill_path.endswith("/SKILL.md"):
        return skill_path[: -len("/SKILL.md")]
    return skill_path


def _drop_lock_entry(name: str) -> None:
    lock = core.lock_load()
    if lock.get("skills", {}).pop(name, None) is not None:
        core.lock_save(lock)


def _migrate_one(name: str, entry: dict) -> None:
    paths = core.paths_for(name)
    if paths.dir.exists():
        _drop_lock_entry(name)
        return

    src = core.npx_skill_dir(name)
    repo = entry["source"]
    path = _path_from_skillpath(entry["skillPath"])
    core.copy_tree(src, paths.current)
    # skillFolderHash is the git tree hash of the skill folder at install time.
    with core.fetch_matching(repo, path, entry["skillFolderHash"]) as match:
        if match is None:
            # Upstream history no longer holds that tree (rewritten or moved).
            core.copy_tree(src, paths.baseline)
            commit = None
        else:
            core.copy_tree(match.dir, paths.baseline)
            commit = match.commit
    core.source_save(name, repo, path, commit)
    core.link(name)
    core.log_append(name, "migrate", f"{repo}@{commit}" if commit else f"{repo}, no matching commit")
    _drop_lock_entry(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate.py")
    parser.add_argument("name", nargs="?")
    args = parser.parse_args(argv)

    skills = core.lock_load().get("skills", {})

    if args.name is not None:
        entry = skills.get(args.name)
        if entry is None:
            return 0
        _migrate_one(args.name, entry)
        return 0

    for name, entry in list(skills.items()):
        _migrate_one(name, entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
