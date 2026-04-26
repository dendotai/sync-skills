import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    (h / ".claude" / "skills").mkdir(parents=True)
    return h


@pytest.fixture
def fake_upstream_repo(tmp_path):
    """Factory: build a local git repo with given files at given subpath.

    Usage:
        repo_url = fake_upstream_repo("acme/widget", "skills/widget", {
            "SKILL.md": "---\\nname: widget\\n---\\n# v1\\n",
        })
    """
    counter = {"n": 0}

    def _make(repo_id: str, subpath: str, files: dict[str, str], extra_commits: list[dict[str, str]] | None = None) -> str:
        counter["n"] += 1
        repo_dir = tmp_path / f"upstream-{counter['n']}"
        repo_dir.mkdir()
        run = lambda *a: subprocess.run(a, cwd=repo_dir, check=True, capture_output=True)
        run("git", "init", "-q", "-b", "main")
        run("git", "config", "user.email", "test@test")
        run("git", "config", "user.name", "test")
        target = repo_dir / subpath
        target.mkdir(parents=True, exist_ok=True)
        for rel, content in files.items():
            p = target / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        run("git", "add", "-A")
        run("git", "commit", "-q", "-m", "initial")
        for commit in extra_commits or []:
            for rel, content in commit.items():
                (target / rel).write_text(content)
            run("git", "add", "-A")
            run("git", "commit", "-q", "-m", "update")
        return f"file://{repo_dir}"

    return _make
