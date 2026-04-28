"""Diagnose state drift across sync-skills, vercel-labs/skills, and the Claude
symlink directory. Each diagnosis is independently callable; a fix is attached
to every Issue so callers can apply selectively."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sync_skills as core


def _npx_dir(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".agents" / "skills" / name


def _lock_save(data: dict) -> None:
    (Path(os.environ["HOME"]) / ".agents" / ".skill-lock.json").write_text(
        json.dumps(data, indent=2) + "\n"
    )


@dataclass
class Issue:
    kind: str
    skill: str
    summary: str
    apply: Callable[[], None]


def _fix_symlink(name: str) -> Callable[[], None]:
    def apply() -> None:
        paths = core.paths_for(name)
        paths.symlink.parent.mkdir(parents=True, exist_ok=True)
        if paths.symlink.is_symlink() or paths.symlink.exists():
            paths.symlink.unlink()
        paths.symlink.symlink_to(paths.active)
        core.audit_append("doctor-fix", name)

    return apply


def _import_stranded_edit(name: str) -> Callable[[], None]:
    def apply() -> None:
        src = _npx_dir(name) / "SKILL.md"
        dst = core.paths_for(name).active / "SKILL.md"
        shutil.copy2(src, dst)
        core.audit_append("doctor-fix", name)

    return apply


def _check_symlinks() -> list[Issue]:
    issues: list[Issue] = []
    for name in core.registry_load():
        paths = core.paths_for(name)
        if not paths.active.is_dir():
            continue
        if paths.symlink.is_symlink() and paths.symlink.resolve() == paths.active.resolve():
            continue
        if paths.symlink.exists() and not paths.symlink.is_symlink():
            continue

        if core.is_clobbered(name):
            issues.append(
                Issue(
                    kind="symlink-clobber",
                    skill=name,
                    summary=f"~/.claude/skills/{name} points into ~/.agents/skills/{name} (vercel clobber)",
                    apply=_fix_symlink(name),
                )
            )
            if core.has_stranded_edit(name):
                issues.append(
                    Issue(
                        kind="stranded-edit",
                        skill=name,
                        summary=f"~/.agents/skills/{name}/SKILL.md has edits not in active/",
                        apply=_import_stranded_edit(name),
                    )
                )
        else:
            issues.append(
                Issue(
                    kind="symlink-missing",
                    skill=name,
                    summary=f"~/.claude/skills/{name} missing or points to wrong target",
                    apply=_fix_symlink(name),
                )
            )
    return issues


def _drop_registry_entry(name: str) -> Callable[[], None]:
    def apply() -> None:
        data = core.registry_load()
        data.pop(name, None)
        core.registry_save(data)
        core.audit_append("doctor-fix", name)

    return apply


def _check_registry_orphans() -> list[Issue]:
    issues: list[Issue] = []
    for name in core.registry_load():
        if not (core.root() / name).is_dir():
            issues.append(
                Issue(
                    kind="registry-orphan",
                    skill=name,
                    summary=f"sources.json has {name} but ~/.agents/sync-skills/{name}/ is missing",
                    apply=_drop_registry_entry(name),
                )
            )
    return issues


def _delete_folder(name: str) -> Callable[[], None]:
    def apply() -> None:
        shutil.rmtree(core.root() / name)
        core.audit_append("doctor-fix", name)

    return apply


def _check_folder_orphans() -> list[Issue]:
    issues: list[Issue] = []
    sync = core.root()
    if not sync.is_dir():
        return issues
    registered = set(core.registry_load().keys())
    for entry in sorted(sync.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in registered:
            continue
        issues.append(
            Issue(
                kind="folder-orphan",
                skill=entry.name,
                summary=f"~/.agents/sync-skills/{entry.name}/ exists but is not in sources.json",
                apply=_delete_folder(entry.name),
            )
        )
    return issues


def _drop_lock_entry(name: str) -> Callable[[], None]:
    def apply() -> None:
        lock = core.lock_load()
        if lock.get("skills", {}).pop(name, None) is not None:
            _lock_save(lock)
        core.audit_append("doctor-fix", name)

    return apply


def _check_double_managed() -> list[Issue]:
    issues: list[Issue] = []
    locked = set(core.lock_load().get("skills", {}).keys())
    for name in core.registry_load():
        if name in locked:
            issues.append(
                Issue(
                    kind="double-managed",
                    skill=name,
                    summary=f"{name} is in both sources.json and .skill-lock.json",
                    apply=_drop_lock_entry(name),
                )
            )
    return issues


def _refetch_missing_layers(name: str, missing: list[str]) -> Callable[[], None]:
    def apply() -> None:
        entry = core.registry_get(name) or {}
        paths = core.paths_for(name)
        with core.fetch(entry["repo"], entry["path"], entry.get("ref", "HEAD")) as src:
            for layer in missing:
                core.copy_tree(src, getattr(paths, layer))
        core.audit_append("doctor-fix", name)

    return apply


def _check_missing_layers() -> list[Issue]:
    issues: list[Issue] = []
    for name in core.registry_load():
        paths = core.paths_for(name)
        if not (core.root() / name).is_dir():
            continue
        missing = [
            layer for layer in ("active", "baseline", "upstream")
            if not getattr(paths, layer).is_dir()
        ]
        if missing:
            issues.append(
                Issue(
                    kind="missing-layers",
                    skill=name,
                    summary=f"{name} is missing layer(s): {', '.join(missing)}",
                    apply=_refetch_missing_layers(name, missing),
                )
            )
    return issues


def diagnose() -> list[Issue]:
    return (
        _check_symlinks()
        + _check_registry_orphans()
        + _check_folder_orphans()
        + _check_double_managed()
        + _check_missing_layers()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor.py")
    parser.add_argument("--yes", action="store_true", help="apply every proposed fix without prompting")
    args = parser.parse_args(argv)

    issues = diagnose()
    if not issues:
        print("clean bill of health")
        return 0

    print(f"found {len(issues)} issue(s):")
    for i in issues:
        print(f"  [{i.kind}] {i.summary}")

    if not args.yes:
        print("\nre-run with --yes to apply every proposed fix.")
        return 0

    for i in issues:
        i.apply()
        print(f"fixed: [{i.kind}] {i.skill}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
