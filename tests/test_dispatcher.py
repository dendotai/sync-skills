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


def test_fetch_all_refreshes_upstream_tree_and_emits_names(home, fake_upstream_repo):
    repo = fake_upstream_repo("acme/skills", "skills/widget", {"SKILL.md": "v2\n"})
    registry = home / ".agents" / "sync-skills" / "sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps({"widget": {"repo": repo, "path": "skills/widget", "ref": "HEAD"}})
    )
    upstream = home / ".agents" / "sync-skills" / "widget" / "upstream"
    upstream.mkdir(parents=True)
    (upstream / "STALE.md").write_text("stale\n")

    result = _run("fetch-all")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["widget"]
    assert (upstream / "SKILL.md").read_text() == "v2\n"
    assert not (upstream / "STALE.md").exists()


def _seed_layered_skill(home, name, baseline_content, upstream_content):
    base = home / ".agents" / "sync-skills" / name
    (base / "baseline").mkdir(parents=True)
    (base / "upstream").mkdir(parents=True)
    (base / "baseline" / "SKILL.md").write_text(baseline_content)
    (base / "upstream" / "SKILL.md").write_text(upstream_content)


def test_changed_list_emits_only_skills_whose_baseline_differs_from_upstream(home):
    _seed_registry(home, "alpha")
    _seed_registry(home, "beta")
    _seed_layered_skill(home, "alpha", "v1\n", "v2\n")
    _seed_layered_skill(home, "beta", "v1\n", "v1\n")

    result = _run("changed-list")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["alpha"]


def test_changed_list_emits_nothing_when_no_registry(home):
    result = _run("changed-list")
    assert result.returncode == 0
    assert result.stdout == ""


def test_parse_hunks_emits_json_list_from_stdin_diff():
    diff = (
        "--- a/SKILL.md\n"
        "+++ b/SKILL.md\n"
        "@@ -1,3 +1,3 @@\n"
        " line one\n"
        "-old middle\n"
        "+new middle\n"
        " line three\n"
    )
    result = _run("parse-hunks", input=diff)
    assert result.returncode == 0
    assert json.loads(result.stdout) == [
        {
            "file": "SKILL.md",
            "old_string": "line one\nold middle\nline three\n",
            "new_string": "line one\nnew middle\nline three\n",
        }
    ]


def test_backup_active_creates_bak_and_prints_path(home):
    _seed_active_skill_md(home, "widget", "v1\n")

    result = _run("backup-active", "widget")
    assert result.returncode == 0

    bak = home / ".agents" / "sync-skills" / "widget" / "active" / "SKILL.md.bak"
    assert bak.is_file()
    assert bak.read_text() == "v1\n"
    assert result.stdout.strip() == str(bak)


def test_wholesale_replaces_active_with_upstream_and_audits(home):
    base = home / ".agents" / "sync-skills" / "widget"
    (base / "active").mkdir(parents=True)
    (base / "upstream").mkdir(parents=True)
    (base / "active" / "SKILL.md").write_text("old\n")
    (base / "active" / "stale.md").write_text("gone\n")
    (base / "upstream" / "SKILL.md").write_text("new\n")
    (base / "upstream" / "fresh.md").write_text("added\n")

    result = _run("wholesale", "widget")
    assert result.returncode == 0

    assert (base / "active" / "SKILL.md").read_text() == "new\n"
    assert (base / "active" / "fresh.md").read_text() == "added\n"
    assert not (base / "active" / "stale.md").exists()

    log = home / ".agents" / "sync-skills" / "history.log"
    line = log.read_text().strip().splitlines()[-1]
    _, action, skill = line.split("\t")
    assert action == "wholesale"
    assert skill == "widget"
