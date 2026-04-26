import json

import core
import install


def _install(home, fake_upstream_repo, name="w", content="v\n"):
    repo = fake_upstream_repo(f"acme/{name}", f"skills/{name}", {"SKILL.md": content})
    install.main([name, repo, f"skills/{name}"])


def _make_clobber(home, name="w", npx_content="v\n"):
    npx_dir = home / ".agents" / "skills" / name
    npx_dir.mkdir(parents=True)
    (npx_dir / "SKILL.md").write_text(npx_content)
    link = home / ".claude" / "skills" / name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(npx_dir)


def _seed_lock(home, name, source="x/skills"):
    lock = home / ".agents" / ".skill-lock.json"
    data = json.loads(lock.read_text()) if lock.exists() else {"version": 3, "skills": {}}
    data["skills"][name] = {
        "source": source,
        "skillPath": f"{name}/SKILL.md",
        "skillFolderHash": "h",
    }
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps(data))


def test_is_clobbered_true_when_symlink_points_into_npx_dir(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    _make_clobber(home)
    assert core.is_clobbered("w") is True


def test_is_clobbered_false_when_symlink_points_into_active(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    assert core.is_clobbered("w") is False


def test_is_clobbered_false_when_symlink_missing(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    (home / ".claude" / "skills" / "w").unlink()
    assert core.is_clobbered("w") is False


def test_has_stranded_edit_true_when_npx_skill_md_diverges(home, fake_upstream_repo):
    _install(home, fake_upstream_repo, content="v\n")
    _make_clobber(home, npx_content="HAND-EDITED\n")
    assert core.has_stranded_edit("w") is True


def test_has_stranded_edit_false_when_npx_matches_active(home, fake_upstream_repo):
    _install(home, fake_upstream_repo, content="v\n")
    _make_clobber(home, npx_content="v\n")
    assert core.has_stranded_edit("w") is False


def test_has_stranded_edit_false_when_npx_dir_absent(home, fake_upstream_repo):
    _install(home, fake_upstream_repo)
    assert core.has_stranded_edit("w") is False


def test_migration_candidates_empty_when_lock_file_absent(home):
    assert core.migration_candidates() == []


def test_migration_candidates_lists_locked_skill_with_npx_symlink(home):
    _seed_lock(home, "foo")
    _make_clobber(home, name="foo")
    assert core.migration_candidates() == ["foo"]


def test_migration_candidates_skips_already_registered_skills(home, fake_upstream_repo):
    _install(home, fake_upstream_repo, name="w")
    _seed_lock(home, "w")
    # 'w' is double-managed, not a migration candidate (doctor handles that case).
    assert "w" not in core.migration_candidates()


def test_migration_candidates_skips_locked_skill_without_active_npx_symlink(home):
    _seed_lock(home, "bar")
    # No symlink at ~/.claude/skills/bar — nothing to migrate.
    assert core.migration_candidates() == []


def test_migration_candidates_returns_sorted_names(home):
    _seed_lock(home, "zebra")
    _seed_lock(home, "alpha")
    _make_clobber(home, name="zebra")
    _make_clobber(home, name="alpha")
    assert core.migration_candidates() == ["alpha", "zebra"]
