"""Snap a skill's baseline/ to match its upstream/ (`baseline := upstream`).
Append an `accept` audit event."""

from __future__ import annotations

import argparse
import sys

import sync_skills as core


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="accept.py")
    parser.add_argument("name")
    args = parser.parse_args(argv)

    paths = core.paths_for(args.name)
    core.copy_tree(paths.upstream, paths.baseline)
    core.audit_append("accept", args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
