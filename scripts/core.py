"""Shared helpers for the sync-skills scripts. Imported by each script via the
script's parent dir on sys.path (Python sets that automatically when a script
is invoked directly; tests prepend it via conftest)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


class Paths(NamedTuple):
    active: Path
    baseline: Path
    upstream: Path
    symlink: Path


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
    base = root() / name
    return Paths(
        active=base / "active",
        baseline=base / "baseline",
        upstream=base / "upstream",
        symlink=Path(os.environ["HOME"]) / ".claude" / "skills" / name,
    )


def _npx_skill_dir(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".agents" / "skills" / name


def is_clobbered(name: str) -> bool:
    """True if ~/.claude/skills/<name> symlinks into ~/.agents/skills/<name>."""
    link = paths_for(name).symlink
    if not link.is_symlink():
        return False
    try:
        return link.resolve() == _npx_skill_dir(name).resolve()
    except OSError:
        return False


def _lock_path() -> Path:
    return Path(os.environ["HOME"]) / ".agents" / ".skill-lock.json"


def lock_load() -> dict:
    p = _lock_path()
    if not p.exists():
        return {"version": 3, "skills": {}}
    return json.loads(p.read_text())


def migration_candidates() -> list[str]:
    """Lock-file skills with an active npx-style symlink and no sources.json entry."""
    registered = set(registry_load().keys())
    out: list[str] = []
    for name in lock_load().get("skills", {}):
        if name in registered:
            continue
        if is_clobbered(name):
            out.append(name)
    return sorted(out)


def has_stranded_edit(name: str) -> bool:
    """True if ~/.agents/skills/<name>/SKILL.md differs from active/SKILL.md."""
    npx = _npx_skill_dir(name) / "SKILL.md"
    active = paths_for(name).active / "SKILL.md"
    if not (npx.is_file() and active.is_file()):
        return False
    return npx.read_bytes() != active.read_bytes()


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def backup_active(name: str) -> Path:
    src = paths_for(name).active / "SKILL.md"
    dst = src.with_name("SKILL.md.bak")
    shutil.copy2(src, dst)
    return dst


def _registry_file() -> Path:
    return root() / "sources.json"


def registry_load() -> dict:
    p = _registry_file()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def registry_save(data: dict) -> None:
    p = _registry_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def registry_get(name: str) -> dict | None:
    return registry_load().get(name)


def registry_set(name: str, repo: str, path: str, ref: str = "HEAD") -> None:
    data = registry_load()
    data[name] = {"repo": repo, "path": path, "ref": ref}
    registry_save(data)


def audit_append(action: str, skill: str) -> None:
    log = root() / "history.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log.open("a") as f:
        f.write(f"{ts}\t{action}\t{skill}\n")


def _resolve_url(repo: str) -> str:
    if "://" in repo or repo.startswith("/"):
        return repo
    return f"https://github.com/{repo}.git"


@contextmanager
def fetch(repo: str, path: str, ref: str = "HEAD"):
    """Clone repo at ref into a tempdir; yield the path to `path` inside it."""
    url = _resolve_url(repo)
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "clone"
        cmd = ["git", "clone", "--depth", "1"]
        if ref and ref != "HEAD":
            cmd += ["--branch", ref]
        cmd += [url, str(clone_dir)]
        subprocess.run(cmd, check=True, capture_output=True)
        skill_dir = clone_dir / path if path and path != "." else clone_dir
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"path {path!r} not found in {repo}")
        yield skill_dir
