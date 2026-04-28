import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_skills.py"


def _run(*args, **kwargs):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        **kwargs,
    )


def test_registry_list_emits_empty_object_when_no_registry(home):
    result = _run("registry-list")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


def test_registry_list_emits_registry_contents(home):
    registry = home / ".agents" / "sync-skills" / "sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps({"widget": {"repo": "acme/skills", "path": "widget", "ref": "HEAD"}})
    )

    result = _run("registry-list")
    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "widget": {"repo": "acme/skills", "path": "widget", "ref": "HEAD"}
    }


def _seed_lock(home, name):
    lock = home / ".agents" / ".skill-lock.json"
    data = json.loads(lock.read_text()) if lock.exists() else {"version": 3, "skills": {}}
    data["skills"][name] = {
        "source": "x/skills",
        "skillPath": f"{name}/SKILL.md",
        "skillFolderHash": "h",
    }
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(data))


def _make_clobber(home, name):
    npx_dir = home / ".agents" / "skills" / name
    npx_dir.mkdir(parents=True)
    (npx_dir / "SKILL.md").write_text("v\n")
    link = home / ".claude" / "skills" / name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(npx_dir)


def test_migration_candidates_lists_sorted_clobbered_locked_names(home):
    _seed_lock(home, "zebra")
    _seed_lock(home, "alpha")
    _make_clobber(home, "zebra")
    _make_clobber(home, "alpha")

    result = _run("migration-candidates")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["alpha", "zebra"]


def test_migration_candidates_emits_nothing_when_none(home):
    result = _run("migration-candidates")
    assert result.returncode == 0
    assert result.stdout == ""


def _seed_registry(home, name):
    registry = home / ".agents" / "sync-skills" / "sources.json"
    data = json.loads(registry.read_text()) if registry.exists() else {}
    data[name] = {"repo": "acme/skills", "path": name, "ref": "HEAD"}
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(data))


def test_clobbered_list_emits_only_registered_clobbered_names(home):
    _seed_registry(home, "alpha")
    _seed_registry(home, "beta")
    _make_clobber(home, "alpha")
    # beta is registered but not clobbered → excluded.
    # gamma is clobbered but unregistered → also excluded.
    _make_clobber(home, "gamma")

    result = _run("clobbered-list")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["alpha"]


def test_clobbered_list_emits_nothing_when_no_registry(home):
    result = _run("clobbered-list")
    assert result.returncode == 0
    assert result.stdout == ""


def _seed_active_skill_md(home, name, content):
    active = home / ".agents" / "sync-skills" / name / "active"
    active.mkdir(parents=True, exist_ok=True)
    (active / "SKILL.md").write_text(content)


def _seed_npx_skill_md(home, name, content):
    npx = home / ".agents" / "skills" / name
    npx.mkdir(parents=True, exist_ok=True)
    (npx / "SKILL.md").write_text(content)


def test_stranded_edit_exits_zero_when_npx_diverges_from_active(home):
    _seed_active_skill_md(home, "alpha", "v1\n")
    _seed_npx_skill_md(home, "alpha", "HAND-EDITED\n")

    result = _run("stranded-edit", "alpha")
    assert result.returncode == 0


def test_stranded_edit_exits_one_when_npx_matches_active(home):
    _seed_active_skill_md(home, "alpha", "v1\n")
    _seed_npx_skill_md(home, "alpha", "v1\n")

    result = _run("stranded-edit", "alpha")
    assert result.returncode == 1


def test_audit_subcommand_appends_history_log(home):
    result = _run("audit", "cherry-pick", "widget")
    assert result.returncode == 0

    log = home / ".agents" / "sync-skills" / "history.log"
    line = log.read_text().strip().splitlines()[-1]
    ts, action, skill = line.split("\t")
    assert action == "cherry-pick"
    assert skill == "widget"


def test_help_lists_audit_subcommand():
    result = _run("--help")
    assert result.returncode == 0
    assert "audit" in result.stdout
