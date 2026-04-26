import argparse
import sys

from .lib import registry


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="list.py").parse_args(argv)
    data = registry.load()
    if not data:
        print("no skills registered")
        return 0
    for name in sorted(data):
        entry = data[name]
        print(f"{name}\t{entry['repo']}\t{entry['path']}\t{entry['ref']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
