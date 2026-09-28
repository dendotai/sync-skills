"""Install a skill from upstream: seed current/ and baseline/, write
source.json, create the ~/.claude/skills/<name> symlink, start history.log."""

from __future__ import annotations

import argparse
import sys

import sync_skills as core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install.py")
    parser.add_argument("name")
    parser.add_argument("repo", help="owner/repo or any URL/path git can clone")
    parser.add_argument("path", help="subdirectory inside the repo where the skill lives, or '.' for repo root")
    parser.add_argument("ref", nargs="?", default="HEAD")
    args = parser.parse_args(argv)

    paths = core.paths_for(args.name)
    if paths.dir.exists():
        print(f"error: {args.name} already installed", file=sys.stderr)
        return 2

    with core.fetch(args.repo, args.path, args.ref) as src:
        core.copy_tree(src.dir, paths.current)
        core.copy_tree(src.dir, paths.baseline)
    core.source_save(args.name, args.repo, args.path, src.commit)
    core.link(args.name)
    core.log_append(args.name, "install", f"{args.repo}@{src.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
