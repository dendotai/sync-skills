"""Port skills installed via `npx skills` (vercel-labs/skills) into sync-skills.

Reads ~/.agents/.skill-lock.json, copies ~/.agents/skills/<name>/ into all three
trees, replaces the ~/.claude/skills/<name> symlink with one into active/,
registers the entry, and removes it from the lock file."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import sync_skills as core


def _lock_path() -> Path:
    return Path(os.environ["HOME"]) / ".agents" / ".skill-lock.json"


def _npx_skill_dir(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".agents" / "skills" / name


def _lock_load() -> dict:
    p = _lock_path()
    if not p.exists():
        return {"version": 3, "skills": {}}
    return json.loads(p.read_text())


def _lock_save(data: dict) -> None:
    _lock_path().write_text(json.dumps(data, indent=2) + "\n")


def _path_from_skillpath(skill_path: str) -> str:
    if skill_path.endswith("/SKILL.md"):
        return skill_path[: -len("/SKILL.md")]
    return skill_path


def _drop_lock_entry(name: str) -> None:
    lock = _lock_load()
    if lock.get("skills", {}).pop(name, None) is not None:
        _lock_save(lock)


def _migrate_one(name: str, entry: dict) -> None:
    if core.registry_get(name) is not None:
        _drop_lock_entry(name)
        return

    src = _npx_skill_dir(name)
    paths = core.paths_for(name)
    for dst in (paths.active, paths.baseline, paths.upstream):
        core.copy_tree(src, dst)

    paths.symlink.parent.mkdir(parents=True, exist_ok=True)
    if paths.symlink.is_symlink() or paths.symlink.exists():
        paths.symlink.unlink()
    paths.symlink.symlink_to(paths.active)

    repo = entry["source"]
    path = _path_from_skillpath(entry["skillPath"])
    # skillFolderHash is a content fingerprint (tree hash), not a fetchable
    # git commit; pin to HEAD so fetch-all keeps working post-migrate.
    core.registry_set(name, repo, path, "HEAD")
    core.audit_append("migrate", name)
    _drop_lock_entry(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate.py")
    parser.add_argument("name", nargs="?")
    args = parser.parse_args(argv)

    lock = _lock_load()
    skills = lock.get("skills", {})

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
