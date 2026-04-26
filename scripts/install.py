import argparse
import sys

from .lib import audit, fetcher, layout, registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install.py")
    parser.add_argument("name")
    parser.add_argument("repo")
    parser.add_argument("path")
    parser.add_argument("ref", nargs="?", default="HEAD")
    args = parser.parse_args(argv)

    if registry.get(args.name) is not None:
        print(f"error: {args.name} already registered", file=sys.stderr)
        return 2

    paths = layout.paths_for(args.name)
    with fetcher.fetch(args.repo, args.path, args.ref) as src:
        for dst in (paths.active, paths.baseline, paths.upstream):
            layout.copy_tree(src, dst)

    paths.symlink.parent.mkdir(parents=True, exist_ok=True)
    if paths.symlink.is_symlink() or paths.symlink.exists():
        paths.symlink.unlink()
    paths.symlink.symlink_to(paths.active)

    registry.set(args.name, args.repo, args.path, args.ref)
    audit.append("install", args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
