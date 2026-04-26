"""Register a skill, seed active/baseline/upstream from upstream, create the
~/.claude/skills/<name> symlink, append an audit event."""

from __future__ import annotations

import argparse
import sys

import core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install.py")
    parser.add_argument("name")
    parser.add_argument("repo", help="owner/repo or any URL/path git can clone")
    parser.add_argument("path", help="subdirectory inside the repo where the skill lives, or '.' for repo root")
    parser.add_argument("ref", nargs="?", default="HEAD")
    args = parser.parse_args(argv)

    if core.registry_get(args.name) is not None:
        print(f"error: {args.name} already registered", file=sys.stderr)
        return 2

    paths = core.paths_for(args.name)
    with core.fetch(args.repo, args.path, args.ref) as src:
        for dst in (paths.active, paths.baseline, paths.upstream):
            core.copy_tree(src, dst)

    paths.symlink.parent.mkdir(parents=True, exist_ok=True)
    if paths.symlink.is_symlink() or paths.symlink.exists():
        paths.symlink.unlink()
    paths.symlink.symlink_to(paths.active)

    core.registry_set(args.name, args.repo, args.path, args.ref)
    core.audit_append("install", args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
