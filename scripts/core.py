"""Shared helpers for the sync-skills scripts. Imported by each script via the
script's parent dir on sys.path (Python sets that automatically when a script
is invoked directly; tests prepend it via conftest)."""

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple


class Paths(NamedTuple):
    active: Path
    baseline: Path
    upstream: Path
    symlink: Path


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


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


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
