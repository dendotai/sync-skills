import json
import shutil
import subprocess
from pathlib import Path

import doctor
import install


def _install(home, fake_upstream_repo, name="w", content="v\n"):
    repo = fake_upstream_repo(f"acme/{name}", f"skills/{name}", {"SKILL.md": content})
    install.main([name, repo, f"skills/{name}"])
    return repo


def _base(home, name="w"):
    return home / ".agents" / "sync-skills" / "skills" / name


def _actions(home, name="w"):
    return [line.split("\t")[1] for line in (_base(home, name) / "history.log").read_text().splitlines()]


def test_diagnose_clean_state_returns_no_issues(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    assert doctor.diagnose() == []


def test_diagnose_flags_missing_symlink(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()

    kinds = [(i.kind, i.skill) for i in doctor.diagnose()]
    assert ("symlink-missing", "w") in kinds


def test_fix_recreates_missing_symlink_with_log_line(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    link = home / ".claude" / "skills" / "w"
    link.unlink()

    [issue] = [i for i in doctor.diagnose() if i.kind == "symlink-missing"]
    issue.apply()

    assert link.is_symlink() and link.resolve() == (_base(home) / "current").resolve()
    assert _actions(home)[-1] == "doctor-fix"


def test_diagnose_flags_symlink_pointing_to_wrong_target(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    link = home / ".claude" / "skills" / "w"
    elsewhere = home / "elsewhere"
    elsewhere.mkdir()
    link.unlink()
    link.symlink_to(elsewhere)

    assert any(i.kind == "symlink-missing" and i.skill == "w" for i in doctor.diagnose())


def _make_clobber(home, name="w", npx_content="v\n"):
    """Lay down ~/.agents/skills/<name>/ and point ~/.claude/skills/<name> at it."""
    npx_dir = home / ".agents" / "skills" / name
    npx_dir.mkdir(parents=True)
    (npx_dir / "SKILL.md").write_text(npx_content)
    link = home / ".claude" / "skills" / name
    link.unlink()
    link.symlink_to(npx_dir)


def test_diagnose_flags_vercel_clobber_separately_from_generic_wrong_target(
    home, fake_upstream_repo
):
    _install(home, fake_upstream_repo)
    _make_clobber(home)

    kinds = [i.kind for i in doctor.diagnose() if i.skill == "w"]
    assert "symlink-clobber" in kinds
    assert "symlink-missing" not in kinds


def test_fix_clobber_resymlinks_to_current_with_log_line(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home)

    [issue] = [i for i in doctor.diagnose() if i.kind == "symlink-clobber"]
    issue.apply()

    link = home / ".claude" / "skills" / "w"
    assert link.resolve() == (_base(home) / "current").resolve()
    assert _actions(home)[-1] == "doctor-fix"


def test_diagnose_flags_stranded_edit_when_npx_skill_diverges_from_current(
    home, fake_upstream_repo
):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="HAND-EDITED\n")

    kinds = [i.kind for i in doctor.diagnose() if i.skill == "w"]
    assert "stranded-edit" in kinds
    assert "symlink-clobber" in kinds


def test_no_stranded_edit_when_npx_matches_current(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="v\n")

    kinds = [i.kind for i in doctor.diagnose() if i.skill == "w"]
    assert "stranded-edit" not in kinds


def test_fix_stranded_edit_imports_npx_file_into_current(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="HAND-EDITED\n")

    [issue] = [i for i in doctor.diagnose() if i.kind == "stranded-edit"]
    issue.apply()

    assert (_base(home) / "current" / "SKILL.md").read_text() == "HAND-EDITED\n"


def test_diagnose_ignores_files_at_sync_root(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    sync = home / ".agents" / "sync-skills"
    (sync / "notes.txt").write_text("x\n")
    (sync / "stray").mkdir()

    assert doctor.diagnose() == []


def _seed_lock_entry(home, name):
    lock = home / ".agents" / ".skill-lock.json"
    data = json.loads(lock.read_text()) if lock.exists() else {"version": 3, "skills": {}}
    data["skills"][name] = {
        "source": "x/skills",
        "skillPath": f"{name}/SKILL.md",
        "skillFolderHash": "h",
    }
    lock.write_text(json.dumps(data))


def test_diagnose_flags_double_managed_skill(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _seed_lock_entry(home, "w")

    assert any(i.kind == "double-managed" and i.skill == "w" for i in doctor.diagnose())


def test_fix_double_managed_removes_lock_entry(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _seed_lock_entry(home, "w")

    [issue] = [i for i in doctor.diagnose() if i.kind == "double-managed"]
    issue.apply()

    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert "w" not in lock["skills"]
    assert _actions(home)[-1] == "doctor-fix"


def test_fix_missing_baseline_refetches_at_recorded_commit(home, fake_upstream_repo):
    repo = _install(home, fake_upstream_repo, content="seeded\n")
    repo_dir = Path(repo.removeprefix("file://"))
    (repo_dir / "skills" / "w" / "SKILL.md").write_text("newer upstream\n")
    subprocess.run(["git", "commit", "-qam", "v2"], cwd=repo_dir, check=True)
    shutil.rmtree(_base(home) / "baseline")

    [issue] = [i for i in doctor.diagnose() if i.kind == "missing-layer"]
    assert "baseline" in issue.summary
    issue.apply()

    assert (_base(home) / "baseline" / "SKILL.md").read_text() == "seeded\n"
    assert _actions(home)[-1] == "doctor-fix"


def test_missing_baseline_without_recorded_commit_has_no_fix(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    source = _base(home) / "source.json"
    source.write_text(json.dumps({**json.loads(source.read_text()), "commit": None}))
    shutil.rmtree(_base(home) / "baseline")

    [issue] = [i for i in doctor.diagnose() if i.kind == "missing-layer"]
    assert issue.apply is None


def test_missing_current_is_reported_with_no_fix(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    shutil.rmtree(_base(home) / "current")

    [issue] = [i for i in doctor.diagnose() if i.kind == "missing-layer"]
    assert "current" in issue.summary
    assert issue.apply is None


def test_main_clean_state_prints_clean_bill_and_exits_zero(home, fake_upstream_repo, capsys):
    _install(home, fake_upstream_repo)
    rc = doctor.main([])
    assert rc == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_main_with_yes_applies_every_fix_and_rerun_is_clean(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()
    _seed_lock_entry(home, "w")
    shutil.rmtree(_base(home) / "baseline")

    rc = doctor.main(["--yes"])
    assert rc == 0
    assert doctor.diagnose() == []


def test_main_with_yes_reports_findings_it_cannot_fix(home, fake_upstream_repo, capsys):
    _install(home, fake_upstream_repo)
    shutil.rmtree(_base(home) / "current")

    rc = doctor.main(["--yes"])

    assert rc == 0
    assert "no fix" in capsys.readouterr().out
    assert [i.kind for i in doctor.diagnose()] == ["missing-layer"]


def test_main_without_yes_lists_findings_and_does_not_apply(home, fake_upstream_repo, capsys):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()

    rc = doctor.main([])

    assert rc == 0
    out = capsys.readouterr().out
    assert "symlink-missing" in out
    assert "--yes" in out
    assert not (home / ".claude" / "skills" / "w").exists()
