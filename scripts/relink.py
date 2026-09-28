"""Recreate every ~/.claude/skills/<name> symlink from the folders under
~/.agents/sync-skills/skills/. Idempotent. Cross-machine restore: drop a saved
~/.agents/sync-skills/ folder on a fresh machine, run this, get all
Claude-visible symlinks back."""

from __future__ import annotations

import argparse
import sys

import sync_skills as core


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="relink.py").parse_args(argv)

    rc = 0
    for name in core.managed():
        paths = core.paths_for(name)
        if not paths.current.is_dir():
            print(f"skipping {name}: missing {paths.current}", file=sys.stderr)
            rc = 1
            continue
        if paths.symlink.is_symlink() and paths.symlink.resolve() == paths.current.resolve():
            continue
        if paths.symlink.exists() and not paths.symlink.is_symlink():
            print(f"refusing to overwrite non-symlink at {paths.symlink} ({name})", file=sys.stderr)
            rc = 1
            continue
        core.link(name)
        core.log_append(name, "relink")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
