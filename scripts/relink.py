"""Recreate every ~/.claude/skills/<name> symlink from sources.json.
Idempotent. Cross-machine restore: drop a saved ~/.agents/sync-skills/ folder
on a fresh machine, run this, get all Claude-visible symlinks back."""

from __future__ import annotations

import argparse
import sys

import core


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="relink.py").parse_args(argv)

    rc = 0
    for name in core.registry_load():
        paths = core.paths_for(name)
        if not paths.active.is_dir():
            print(f"skipping {name}: missing {paths.active}", file=sys.stderr)
            rc = 1
            continue
        if paths.symlink.is_symlink() and paths.symlink.resolve() == paths.active.resolve():
            continue
        if paths.symlink.exists() and not paths.symlink.is_symlink():
            print(f"refusing to overwrite non-symlink at {paths.symlink} ({name})", file=sys.stderr)
            rc = 1
            continue
        paths.symlink.parent.mkdir(parents=True, exist_ok=True)
        if paths.symlink.is_symlink():
            paths.symlink.unlink()
        paths.symlink.symlink_to(paths.active)
        core.audit_append("relink", name)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
