import install
import relink


def test_relink_creates_missing_symlink(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    link = home / ".claude" / "skills" / "w"
    link.unlink()
    assert not link.exists()

    rc = relink.main([])
    assert rc == 0

    target = home / ".agents" / "sync-skills" / "w" / "active"
    assert link.is_symlink()
    assert link.resolve() == target.resolve()


def test_relink_skips_skill_with_missing_active(home, fake_upstream_repo, capsys):
    import shutil

    repo_a = fake_upstream_repo("acme/a", "skills/a", {"SKILL.md": "a\n"})
    repo_b = fake_upstream_repo("acme/b", "skills/b", {"SKILL.md": "b\n"})
    install.main(["a", repo_a, "skills/a"])
    install.main(["b", repo_b, "skills/b"])

    sync_root = home / ".agents" / "sync-skills"
    shutil.rmtree(sync_root / "a" / "active")

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc != 0

    assert not (skills_dir / "a").exists()
    assert (skills_dir / "b").resolve() == (sync_root / "b" / "active").resolve()

    err = capsys.readouterr().err
    assert "a" in err


def test_relink_appends_audit_event_per_relinked_skill(home, fake_upstream_repo):
    repo_a = fake_upstream_repo("acme/a", "skills/a", {"SKILL.md": "a\n"})
    repo_b = fake_upstream_repo("acme/b", "skills/b", {"SKILL.md": "b\n"})
    install.main(["a", repo_a, "skills/a"])
    install.main(["b", repo_b, "skills/b"])

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    relink.main([])

    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    relink_lines = [line for line in history if "\trelink\t" in line]
    assert len(relink_lines) == 2
    assert any(line.endswith("\ta") for line in relink_lines)
    assert any(line.endswith("\tb") for line in relink_lines)


def test_relink_empty_registry_is_clean_exit(home):
    rc = relink.main([])
    assert rc == 0
    history = home / ".agents" / "sync-skills" / "history.log"
    assert not history.exists()


def test_relink_refuses_to_overwrite_non_symlink(home, fake_upstream_repo, capsys):
    repo_a = fake_upstream_repo("acme/a", "skills/a", {"SKILL.md": "a\n"})
    repo_b = fake_upstream_repo("acme/b", "skills/b", {"SKILL.md": "b\n"})
    install.main(["a", repo_a, "skills/a"])
    install.main(["b", repo_b, "skills/b"])

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "a").write_text("hand-rolled\n")
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc != 0

    assert (skills_dir / "a").is_file() and not (skills_dir / "a").is_symlink()
    assert (skills_dir / "a").read_text() == "hand-rolled\n"

    sync_root = home / ".agents" / "sync-skills"
    assert (skills_dir / "b").resolve() == (sync_root / "b" / "active").resolve()

    err = capsys.readouterr().err
    assert "a" in err


def test_relink_is_noop_when_symlink_already_correct(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    history = home / ".agents" / "sync-skills" / "history.log"
    before = history.read_text()

    rc = relink.main([])
    assert rc == 0

    assert history.read_text() == before


def test_relink_replaces_wrong_target(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    link = home / ".claude" / "skills" / "w"
    elsewhere = home / "elsewhere"
    elsewhere.mkdir()
    link.unlink()
    link.symlink_to(elsewhere)

    rc = relink.main([])
    assert rc == 0

    target = home / ".agents" / "sync-skills" / "w" / "active"
    assert link.resolve() == target.resolve()


def test_relink_handles_multiple_skills(home, fake_upstream_repo):
    repo_a = fake_upstream_repo("acme/a", "skills/a", {"SKILL.md": "a\n"})
    repo_b = fake_upstream_repo("acme/b", "skills/b", {"SKILL.md": "b\n"})
    install.main(["a", repo_a, "skills/a"])
    install.main(["b", repo_b, "skills/b"])

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc == 0

    sync_root = home / ".agents" / "sync-skills"
    assert (skills_dir / "a").resolve() == (sync_root / "a" / "active").resolve()
    assert (skills_dir / "b").resolve() == (sync_root / "b" / "active").resolve()
