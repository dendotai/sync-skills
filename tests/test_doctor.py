import doctor
import install


def _install(home, fake_upstream_repo, name="w", content="v\n"):
    repo = fake_upstream_repo(f"acme/{name}", f"skills/{name}", {"SKILL.md": content})
    install.main([name, repo, f"skills/{name}"])


def test_diagnose_clean_state_returns_no_issues(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    assert doctor.diagnose() == []


def test_diagnose_flags_missing_symlink(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()

    issues = doctor.diagnose()
    kinds = [(i.kind, i.skill) for i in issues]
    assert ("symlink-missing", "w") in kinds


def test_fix_recreates_missing_symlink_with_audit(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    link = home / ".claude" / "skills" / "w"
    link.unlink()

    [issue] = [i for i in doctor.diagnose() if i.kind == "symlink-missing"]
    issue.apply()

    target = home / ".agents" / "sync-skills" / "w" / "active"
    assert link.is_symlink() and link.resolve() == target.resolve()
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert any("\tdoctor-fix\t" in line and line.endswith("\tw") for line in history)


def test_diagnose_flags_symlink_pointing_to_wrong_target(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    link = home / ".claude" / "skills" / "w"
    elsewhere = home / "elsewhere"
    elsewhere.mkdir()
    link.unlink()
    link.symlink_to(elsewhere)

    issues = doctor.diagnose()
    assert any(i.kind == "symlink-missing" and i.skill == "w" for i in issues)


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

    issues = doctor.diagnose()
    kinds = [i.kind for i in issues if i.skill == "w"]
    assert "symlink-clobber" in kinds
    assert "symlink-missing" not in kinds


def test_fix_clobber_resymlinks_to_active_with_audit(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home)

    [issue] = [i for i in doctor.diagnose() if i.kind == "symlink-clobber"]
    issue.apply()

    link = home / ".claude" / "skills" / "w"
    target = home / ".agents" / "sync-skills" / "w" / "active"
    assert link.resolve() == target.resolve()
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert any("\tdoctor-fix\t" in line and line.endswith("\tw") for line in history)


def test_diagnose_flags_stranded_edit_when_npx_skill_diverges_from_active(
    home, fake_upstream_repo
):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="HAND-EDITED\n")

    issues = doctor.diagnose()
    kinds = [i.kind for i in issues if i.skill == "w"]
    assert "stranded-edit" in kinds
    assert "symlink-clobber" in kinds


def test_no_stranded_edit_when_npx_matches_active(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="v\n")

    kinds = [i.kind for i in doctor.diagnose() if i.skill == "w"]
    assert "stranded-edit" not in kinds


def test_fix_stranded_edit_imports_npx_file_into_active(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home, npx_content="HAND-EDITED\n")

    [issue] = [i for i in doctor.diagnose() if i.kind == "stranded-edit"]
    issue.apply()

    active_skill = home / ".agents" / "sync-skills" / "w" / "active" / "SKILL.md"
    assert active_skill.read_text() == "HAND-EDITED\n"


def test_diagnose_flags_registry_orphan_when_skill_folder_is_missing(
    home, fake_upstream_repo
):
    import shutil as _shutil

    _install(home, fake_upstream_repo)
    _shutil.rmtree(home / ".agents" / "sync-skills" / "w")

    issues = doctor.diagnose()
    kinds = [(i.kind, i.skill) for i in issues]
    assert ("registry-orphan", "w") in kinds


def test_fix_registry_orphan_removes_entry_with_audit(home, fake_upstream_repo):
    import json
    import shutil as _shutil

    _install(home, fake_upstream_repo)
    _shutil.rmtree(home / ".agents" / "sync-skills" / "w")

    [issue] = [i for i in doctor.diagnose() if i.kind == "registry-orphan"]
    issue.apply()

    sources = home / ".agents" / "sync-skills" / "sources.json"
    assert json.loads(sources.read_text()) == {}
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert any("\tdoctor-fix\t" in line and line.endswith("\tw") for line in history)


def test_diagnose_flags_folder_orphan_for_unregistered_directory(home):
    sync = home / ".agents" / "sync-skills"
    (sync / "stray" / "active").mkdir(parents=True)
    (sync / "stray" / "active" / "SKILL.md").write_text("v\n")

    issues = doctor.diagnose()
    assert any(i.kind == "folder-orphan" and i.skill == "stray" for i in issues)


def test_diagnose_ignores_registry_and_history_files_at_sync_root(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    issues = doctor.diagnose()
    assert all(i.skill != "sources.json" for i in issues)
    assert all(i.skill != "history.log" for i in issues)


def test_fix_folder_orphan_deletes_directory(home):
    sync = home / ".agents" / "sync-skills"
    (sync / "stray" / "active").mkdir(parents=True)
    (sync / "stray" / "active" / "SKILL.md").write_text("v\n")

    [issue] = [i for i in doctor.diagnose() if i.kind == "folder-orphan"]
    issue.apply()

    assert not (sync / "stray").exists()


def _seed_lock_entry(home, name):
    import json as _json

    lock = home / ".agents" / ".skill-lock.json"
    data = _json.loads(lock.read_text()) if lock.exists() else {"version": 3, "skills": {}}
    data["skills"][name] = {
        "source": "x/skills",
        "skillPath": f"{name}/SKILL.md",
        "skillFolderHash": "h",
    }
    lock.write_text(_json.dumps(data))


def test_diagnose_flags_double_managed_skill(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _seed_lock_entry(home, "w")

    issues = doctor.diagnose()
    assert any(i.kind == "double-managed" and i.skill == "w" for i in issues)


def test_fix_double_managed_removes_lock_entry(home, fake_upstream_repo):
    import json as _json

    _install(home, fake_upstream_repo)
    _seed_lock_entry(home, "w")

    [issue] = [i for i in doctor.diagnose() if i.kind == "double-managed"]
    issue.apply()

    lock = _json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert "w" not in lock["skills"]
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert any("\tdoctor-fix\t" in line and line.endswith("\tw") for line in history)


def test_diagnose_flags_missing_baseline_layer(home, fake_upstream_repo):
    import shutil as _shutil

    _install(home, fake_upstream_repo)
    _shutil.rmtree(home / ".agents" / "sync-skills" / "w" / "baseline")

    issues = doctor.diagnose()
    assert any(i.kind == "missing-layers" and i.skill == "w" for i in issues)


def test_fix_missing_layers_refetches_from_upstream(home, fake_upstream_repo):
    import shutil as _shutil

    _install(home, fake_upstream_repo, content="seeded\n")
    _shutil.rmtree(home / ".agents" / "sync-skills" / "w" / "baseline")
    _shutil.rmtree(home / ".agents" / "sync-skills" / "w" / "upstream")

    [issue] = [i for i in doctor.diagnose() if i.kind == "missing-layers"]
    issue.apply()

    base = home / ".agents" / "sync-skills" / "w"
    assert (base / "baseline" / "SKILL.md").read_text() == "seeded\n"
    assert (base / "upstream" / "SKILL.md").read_text() == "seeded\n"
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert any("\tdoctor-fix\t" in line and line.endswith("\tw") for line in history)


def test_fix_missing_active_does_not_clobber_when_other_layers_present(
    home, fake_upstream_repo
):
    import shutil as _shutil

    _install(home, fake_upstream_repo, content="seeded\n")
    base = home / ".agents" / "sync-skills" / "w"
    (base / "active" / "SKILL.md").write_text("custom\n")
    _shutil.rmtree(base / "upstream")

    [issue] = [i for i in doctor.diagnose() if i.kind == "missing-layers"]
    issue.apply()

    # Existing active/ stays untouched; only the missing layer is restored.
    assert (base / "active" / "SKILL.md").read_text() == "custom\n"
    assert (base / "upstream" / "SKILL.md").read_text() == "seeded\n"


def test_main_clean_state_prints_clean_bill_and_exits_zero(home, fake_upstream_repo, capsys):
    _install(home, fake_upstream_repo)
    rc = doctor.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "clean" in out.lower()


def test_main_with_yes_applies_every_fix_and_rerun_is_clean(home, fake_upstream_repo):
    import shutil as _shutil

    _install(home, fake_upstream_repo)
    # 1: missing symlink
    (home / ".claude" / "skills" / "w").unlink()
    # 4: orphan folder
    sync = home / ".agents" / "sync-skills"
    (sync / "stray" / "active").mkdir(parents=True)
    (sync / "stray" / "active" / "SKILL.md").write_text("v\n")
    # 5: double-managed
    _seed_lock_entry(home, "w")
    # 6: missing layer
    _shutil.rmtree(sync / "w" / "baseline")

    rc = doctor.main(["--yes"])
    assert rc == 0
    assert doctor.diagnose() == []


def test_main_without_yes_lists_findings_and_does_not_apply(home, fake_upstream_repo, capsys):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()

    rc = doctor.main([])

    assert rc == 0
    out = capsys.readouterr().out
    assert "symlink-missing" in out
    assert "--yes" in out
    # Fix not applied: symlink still missing.
    assert not (home / ".claude" / "skills" / "w").exists()
