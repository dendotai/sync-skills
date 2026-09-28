"""Shared helpers for the sync-skills scripts. Imported by each script via the
script's parent dir on sys.path (Python sets that automatically when a script
is invoked directly; tests prepend it via conftest)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, NamedTuple


class Paths(NamedTuple):
    dir: Path
    current: Path
    baseline: Path
    source: Path
    history: Path
    symlink: Path


class Fetched(NamedTuple):
    dir: Path
    commit: str


@dataclass
class Hunk:
    file: str
    old_string: str
    new_string: str


def parse_hunks(diff_text: str) -> list[Hunk]:
    hunks: list[Hunk] = []
    current_file: str | None = None
    old: list[str] = []
    new: list[str] = []
    in_hunk = False
    last_old = False
    last_new = False

    def flush() -> None:
        if in_hunk and current_file is not None:
            hunks.append(Hunk(current_file, "".join(old), "".join(new)))

    def strip_trailing_newline(buf: list[str]) -> None:
        if buf and buf[-1].endswith("\n"):
            buf[-1] = buf[-1][:-1]

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("+++ "):
            flush()
            in_hunk = False
            path = line[4:].rstrip("\n")
            current_file = path[2:] if path.startswith("b/") else path
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("@@"):
            flush()
            old, new = [], []
            in_hunk = True
            last_old = last_new = False
            continue
        if not in_hunk:
            continue
        if line.startswith("\\"):
            if last_old:
                strip_trailing_newline(old)
            if last_new:
                strip_trailing_newline(new)
            continue
        if line.startswith(" "):
            old.append(line[1:])
            new.append(line[1:])
            last_old = last_new = True
        elif line.startswith("-"):
            old.append(line[1:])
            last_old, last_new = True, False
        elif line.startswith("+"):
            new.append(line[1:])
            last_old, last_new = False, True

    flush()
    return hunks


def root() -> Path:
    return Path(os.environ["HOME"]) / ".agents" / "sync-skills"


def paths_for(name: str) -> Paths:
    base = root() / "skills" / name
    return Paths(
        dir=base,
        current=base / "current",
        baseline=base / "baseline",
        source=base / "source.json",
        history=base / "history.log",
        symlink=Path(os.environ["HOME"]) / ".claude" / "skills" / name,
    )


def managed() -> list[str]:
    skills = root() / "skills"
    if not skills.is_dir():
        return []
    return sorted(p.name for p in skills.iterdir() if p.is_dir())


def source_load(name: str) -> dict:
    return json.loads(paths_for(name).source.read_text())


def source_save(name: str, repo: str, path: str, commit: str | None) -> None:
    p = paths_for(name).source
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"repo": repo, "path": path, "commit": commit}, indent=2) + "\n")


def log_append(name: str, action: str, detail: str = "") -> None:
    log = paths_for(name).history
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts}\t{action}\t{detail}" if detail else f"{ts}\t{action}"
    with log.open("a") as f:
        f.write(line + "\n")


def link(name: str) -> None:
    paths = paths_for(name)
    paths.symlink.parent.mkdir(parents=True, exist_ok=True)
    if paths.symlink.is_symlink() or paths.symlink.exists():
        paths.symlink.unlink()
    paths.symlink.symlink_to(paths.current)


def npx_skill_dir(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".agents" / "skills" / name


def is_clobbered(name: str) -> bool:
    """True if ~/.claude/skills/<name> symlinks into ~/.agents/skills/<name>."""
    link = paths_for(name).symlink
    if not link.is_symlink():
        return False
    try:
        return link.resolve() == npx_skill_dir(name).resolve()
    except OSError:
        return False


def _lock_path() -> Path:
    return Path(os.environ["HOME"]) / ".agents" / ".skill-lock.json"


def lock_load() -> dict:
    p = _lock_path()
    if not p.exists():
        return {"version": 3, "skills": {}}
    return json.loads(p.read_text())


def lock_save(data: dict) -> None:
    _lock_path().write_text(json.dumps(data, indent=2) + "\n")


def migration_candidates() -> list[str]:
    """Lock-file skills whose Claude symlink points into ~/.agents/skills and
    that this tool does not manage yet."""
    ours = set(managed())
    out: list[str] = []
    for name in lock_load().get("skills", {}):
        if name in ours:
            continue
        if is_clobbered(name):
            out.append(name)
    return sorted(out)


def has_stranded_edit(name: str) -> bool:
    """True if ~/.agents/skills/<name>/SKILL.md differs from current/SKILL.md."""
    npx = npx_skill_dir(name) / "SKILL.md"
    current = paths_for(name).current / "SKILL.md"
    if not (npx.is_file() and current.is_file()):
        return False
    return npx.read_bytes() != current.read_bytes()


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git"))


def backup_current(name: str) -> Path:
    src = paths_for(name).current / "SKILL.md"
    dst = src.with_name("SKILL.md.bak")
    shutil.copy2(src, dst)
    return dst


def _resolve_url(repo: str) -> str:
    if "://" in repo or repo.startswith("/"):
        return repo
    return f"https://github.com/{repo}.git"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _skill_dir(clone_dir: Path, repo: str, path: str) -> Path:
    skill_dir = clone_dir / path if path and path != "." else clone_dir
    if not skill_dir.is_dir():
        raise FileNotFoundError(f"path {path!r} not found in {repo}")
    return skill_dir


_SHA_RE = re.compile(r"[0-9a-f]{7,40}")


@contextmanager
def fetch(repo: str, path: str, ref: str = "HEAD") -> Iterator[Fetched]:
    """Shallow-clone repo at ref into a tempdir; yield `path` inside it and the
    commit it was taken from."""
    url = _resolve_url(repo)
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "clone"
        if ref and ref != "HEAD" and _SHA_RE.fullmatch(ref):
            # `git clone --branch` only accepts named refs; for commit SHAs,
            # init + fetch the SHA directly + checkout FETCH_HEAD.
            clone_dir.mkdir()
            _git(clone_dir, "init", "-q")
            _git(clone_dir, "remote", "add", "origin", url)
            _git(clone_dir, "fetch", "--depth", "1", "origin", ref)
            _git(clone_dir, "checkout", "-q", "FETCH_HEAD")
        else:
            cmd = ["git", "clone", "--depth", "1"]
            if ref and ref != "HEAD":
                cmd += ["--branch", ref]
            cmd += [url, str(clone_dir)]
            subprocess.run(cmd, check=True, capture_output=True)
        commit = _git(clone_dir, "rev-parse", "HEAD").strip()
        yield Fetched(_skill_dir(clone_dir, repo, path), commit)


@contextmanager
def fetch_matching(repo: str, path: str, tree: str) -> Iterator[Fetched | None]:
    """Clone repo with full history and yield `path` at the newest commit whose
    tree for `path` is `tree`, or None when no commit has it."""
    url = _resolve_url(repo)
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "clone"
        subprocess.run(["git", "clone", "-q", url, str(clone_dir)], check=True, capture_output=True)
        commits = _git(clone_dir, "rev-list", "HEAD").split()
        spec = "" if path == "." else path
        # One cat-file process answers every `<commit>:<path>` lookup; a commit
        # without the path prints "<spec> missing".
        trees = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname)"],
            cwd=clone_dir,
            input="".join(f"{c}:{spec}\n" for c in commits),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        match = next((c for c, t in zip(commits, trees) if t == tree), None)
        if match is None:
            yield None
            return
        _git(clone_dir, "checkout", "-q", match)
        yield Fetched(_skill_dir(clone_dir, repo, path), match)


def _cmd_audit(args: argparse.Namespace) -> int:
    log_append(args.skill, args.action)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for name in managed():
        print(name)
    return 0


def _cmd_migration_candidates(args: argparse.Namespace) -> int:
    for name in migration_candidates():
        print(name)
    return 0


def _cmd_clobbered_list(args: argparse.Namespace) -> int:
    for name in managed():
        if is_clobbered(name):
            print(name)
    return 0


def _cmd_stranded_edit(args: argparse.Namespace) -> int:
    return 0 if has_stranded_edit(args.name) else 1


def _cmd_backup_current(args: argparse.Namespace) -> int:
    print(backup_current(args.name))
    return 0


def _cmd_parse_hunks(args: argparse.Namespace) -> int:
    hunks = parse_hunks(sys.stdin.read())
    print(json.dumps([h.__dict__ for h in hunks]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_skills.py",
        description="CLI dispatcher for sync-skills helpers used by /sync-skills SKILL.md.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="Append a line to a skill's history.log.")
    p_audit.add_argument("action")
    p_audit.add_argument("skill")
    p_audit.set_defaults(func=_cmd_audit)

    p_list = sub.add_parser("list", help="Emit the names of the managed skills, one per line.")
    p_list.set_defaults(func=_cmd_list)

    p_migration = sub.add_parser(
        "migration-candidates",
        help="Emit names of npx-managed skills this tool does not manage yet.",
    )
    p_migration.set_defaults(func=_cmd_migration_candidates)

    p_clobbered = sub.add_parser(
        "clobbered-list",
        help="Emit names of managed skills whose Claude symlink has been clobbered.",
    )
    p_clobbered.set_defaults(func=_cmd_clobbered_list)

    p_stranded = sub.add_parser(
        "stranded-edit",
        help="Exit 0 if npx-side SKILL.md differs from current/SKILL.md, 1 otherwise.",
    )
    p_stranded.add_argument("name")
    p_stranded.set_defaults(func=_cmd_stranded_edit)

    p_backup = sub.add_parser(
        "backup-current",
        help="Snapshot current/SKILL.md to SKILL.md.bak; print backup path.",
    )
    p_backup.add_argument("name")
    p_backup.set_defaults(func=_cmd_backup_current)

    p_parse = sub.add_parser(
        "parse-hunks",
        help="Read a unified diff on stdin; emit JSON list of {file, old_string, new_string}.",
    )
    p_parse.set_defaults(func=_cmd_parse_hunks)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
