import argparse
import sys

from .lib import layout, registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paths.py")
    parser.add_argument("name")
    args = parser.parse_args(argv)

    if registry.get(args.name) is None:
        print(f"error: {args.name} not registered", file=sys.stderr)
        return 2

    p = layout.paths_for(args.name)
    print(f"active   {p.active}")
    print(f"baseline {p.baseline}")
    print(f"upstream {p.upstream}")
    print(f"symlink  {p.symlink}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
