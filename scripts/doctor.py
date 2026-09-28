"""Diagnose state drift across sync-skills, vercel-labs/skills, and the Claude
symlink directory. Each diagnosis is independently callable; a fix is attached
to every Issue that has one, so callers can apply selectively."""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import sync_skills as core


@dataclass
class Issue:
    kind: str
    skill: str
    summary: str
    apply: Optional[Callable[[], None]]


def _fix_symlink(name: str) -> Callable[[], None]:
    def apply() -> None:
        core.link(name)
        core.log_append(name, "doctor-fix", "symlink")

    return apply


def _import_stranded_edit(name: str) -> Callable[[], None]:
    def apply() -> None:
        src = core.npx_skill_dir(name) / "SKILL.md"
        dst = core.paths_for(name).current / "SKILL.md"
        shutil.copy2(src, dst)
        core.log_append(name, "doctor-fix", "stranded-edit")

    return apply


def _check_symlinks() -> list[Issue]:
    issues: list[Issue] = []
    for name in core.managed():
        paths = core.paths_for(name)
        if not paths.current.is_dir():
            continue
        if paths.symlink.is_symlink() and paths.symlink.resolve() == paths.current.resolve():
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
                        summary=f"~/.agents/skills/{name}/SKILL.md has edits not in current/",
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


def _drop_lock_entry(name: str) -> Callable[[], None]:
    def apply() -> None:
        lock = core.lock_load()
        if lock.get("skills", {}).pop(name, None) is not None:
            core.lock_save(lock)
        core.log_append(name, "doctor-fix", "double-managed")

    return apply


def _check_double_managed() -> list[Issue]:
    issues: list[Issue] = []
    locked = set(core.lock_load().get("skills", {}).keys())
    for name in core.managed():
        if name in locked:
            issues.append(
                Issue(
                    kind="double-managed",
                    skill=name,
                    summary=f"{name} is managed here and also listed in .skill-lock.json",
                    apply=_drop_lock_entry(name),
                )
            )
    return issues


def _refetch_baseline(name: str, source: dict) -> Callable[[], None]:
    def apply() -> None:
        with core.fetch(source["repo"], source["path"], source["commit"]) as src:
            core.copy_tree(src.dir, core.paths_for(name).baseline)
        core.log_append(name, "doctor-fix", f"baseline refetched at {source['commit']}")

    return apply


def _check_missing_layers() -> list[Issue]:
    issues: list[Issue] = []
    for name in core.managed():
        paths = core.paths_for(name)
        if not paths.current.is_dir():
            issues.append(
                Issue(
                    kind="missing-layer",
                    skill=name,
                    summary=f"{name} is missing current/",
                    apply=None,
                )
            )
        if not paths.baseline.is_dir():
            source = core.source_load(name) if paths.source.is_file() else {}
            issues.append(
                Issue(
                    kind="missing-layer",
                    skill=name,
                    summary=f"{name} is missing baseline/",
                    apply=_refetch_baseline(name, source) if source.get("commit") else None,
                )
            )
    return issues


def diagnose() -> list[Issue]:
    return _check_symlinks() + _check_double_managed() + _check_missing_layers()


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
        suffix = "" if i.apply else " (no fix)"
        print(f"  [{i.kind}] {i.summary}{suffix}")

    if not args.yes:
        print("\nre-run with --yes to apply every proposed fix.")
        return 0

    for i in issues:
        if i.apply is None:
            print(f"no fix: [{i.kind}] {i.skill}")
            continue
        i.apply()
        print(f"fixed: [{i.kind}] {i.skill}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
