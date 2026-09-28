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


def _skill_dir(home, name):
    return home / ".agents" / "sync-skills" / "skills" / name


def _seed_managed(home, name):
    (_skill_dir(home, name) / "current").mkdir(parents=True)


def test_list_emits_nothing_when_no_skills(home):
    result = _run("list")
    assert result.returncode == 0
    assert result.stdout == ""


def test_list_emits_sorted_skill_folder_names(home):
    _seed_managed(home, "zebra")
    _seed_managed(home, "alpha")
    (home / ".agents" / "sync-skills" / "skills" / "notes.txt").write_text("x\n")

    result = _run("list")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["alpha", "zebra"]


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


def test_clobbered_list_emits_only_managed_clobbered_names(home):
    _seed_managed(home, "alpha")
    _seed_managed(home, "beta")
    _make_clobber(home, "alpha")
    # beta is managed but not clobbered → excluded.
    # gamma is clobbered but not managed → also excluded.
    _make_clobber(home, "gamma")

    result = _run("clobbered-list")
    assert result.returncode == 0
    assert result.stdout.splitlines() == ["alpha"]


def test_clobbered_list_emits_nothing_when_no_skills(home):
    result = _run("clobbered-list")
    assert result.returncode == 0
    assert result.stdout == ""


def _seed_current_skill_md(home, name, content):
    current = _skill_dir(home, name) / "current"
    current.mkdir(parents=True, exist_ok=True)
    (current / "SKILL.md").write_text(content)


def _seed_npx_skill_md(home, name, content):
    npx = home / ".agents" / "skills" / name
    npx.mkdir(parents=True, exist_ok=True)
    (npx / "SKILL.md").write_text(content)


def test_stranded_edit_exits_zero_when_npx_diverges_from_current(home):
    _seed_current_skill_md(home, "alpha", "v1\n")
    _seed_npx_skill_md(home, "alpha", "HAND-EDITED\n")

    result = _run("stranded-edit", "alpha")
    assert result.returncode == 0


def test_stranded_edit_exits_one_when_npx_matches_current(home):
    _seed_current_skill_md(home, "alpha", "v1\n")
    _seed_npx_skill_md(home, "alpha", "v1\n")

    result = _run("stranded-edit", "alpha")
    assert result.returncode == 1


def test_audit_subcommand_appends_to_the_skill_history_log(home):
    result = _run("audit", "relink", "widget")
    assert result.returncode == 0

    log = _skill_dir(home, "widget") / "history.log"
    ts, action = log.read_text().strip().splitlines()[-1].split("\t")
    assert action == "relink"


def test_help_lists_audit_subcommand():
    result = _run("--help")
    assert result.returncode == 0
    assert "audit" in result.stdout


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


def test_backup_current_creates_bak_and_prints_path(home):
    _seed_current_skill_md(home, "widget", "v1\n")

    result = _run("backup-current", "widget")
    assert result.returncode == 0

    bak = _skill_dir(home, "widget") / "current" / "SKILL.md.bak"
    assert bak.read_text() == "v1\n"
    assert result.stdout.strip() == str(bak)
