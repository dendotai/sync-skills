import builtins
import json
from pathlib import Path

from .layout import root


def _file() -> Path:
    return root() / "sources.json"


def load() -> dict:
    p = _file()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save(data: dict) -> None:
    p = _file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def get(name: str) -> dict | None:
    return load().get(name)


def list() -> builtins.list[str]:
    return sorted(load().keys())


def set(name: str, repo: str, path: str, ref: str = "HEAD") -> None:
    data = load()
    data[name] = {"repo": repo, "path": path, "ref": ref}
    save(data)


def delete(name: str) -> None:
    data = load()
    if data.pop(name, None) is not None:
        save(data)
