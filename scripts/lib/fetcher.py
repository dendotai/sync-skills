import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


def _resolve_url(repo: str) -> str:
    if "://" in repo or repo.startswith("/"):
        return repo
    return f"https://github.com/{repo}.git"


@contextmanager
def fetch(repo: str, path: str, ref: str = "HEAD"):
    """Clone `repo` at `ref` into a tempdir; yield the path to `path` inside it."""
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
