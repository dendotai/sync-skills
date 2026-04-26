import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
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


def exists(name: str, layer: str) -> bool:
    return getattr(paths_for(name), layer).is_dir()


def is_clobbered(name: str) -> bool:
    p = paths_for(name)
    if not p.symlink.is_symlink():
        return True
    return p.symlink.resolve() != p.active.resolve()
