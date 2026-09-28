import shutil

import install
import relink


def _current(home, name):
    return home / ".agents" / "sync-skills" / "skills" / name / "current"


def _history(home, name):
    return home / ".agents" / "sync-skills" / "skills" / name / "history.log"


def _install_ab(home, fake_upstream_repo):
    repo_a = fake_upstream_repo("acme/a", "skills/a", {"SKILL.md": "a\n"})
    repo_b = fake_upstream_repo("acme/b", "skills/b", {"SKILL.md": "b\n"})
    install.main(["a", repo_a, "skills/a"])
    install.main(["b", repo_b, "skills/b"])


def test_relink_creates_missing_symlink(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    link = home / ".claude" / "skills" / "w"
    link.unlink()

    rc = relink.main([])
    assert rc == 0

    assert link.is_symlink()
    assert link.resolve() == _current(home, "w").resolve()


def test_relink_skips_skill_with_missing_current(home, fake_upstream_repo, capsys):
    _install_ab(home, fake_upstream_repo)
    shutil.rmtree(_current(home, "a"))

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc != 0

    assert not (skills_dir / "a").exists()
    assert (skills_dir / "b").resolve() == _current(home, "b").resolve()
    assert "a" in capsys.readouterr().err


def test_relink_appends_log_line_per_relinked_skill(home, fake_upstream_repo):
    _install_ab(home, fake_upstream_repo)

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    relink.main([])

    for name in ("a", "b"):
        actions = [line.split("\t")[1] for line in _history(home, name).read_text().splitlines()]
        assert actions == ["install", "relink"]


def test_relink_with_no_skills_is_clean_exit(home):
    rc = relink.main([])
    assert rc == 0
    assert not (home / ".agents" / "sync-skills").exists()


def test_relink_refuses_to_overwrite_non_symlink(home, fake_upstream_repo, capsys):
    _install_ab(home, fake_upstream_repo)

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "a").write_text("hand-rolled\n")
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc != 0

    assert (skills_dir / "a").is_file() and not (skills_dir / "a").is_symlink()
    assert (skills_dir / "a").read_text() == "hand-rolled\n"
    assert (skills_dir / "b").resolve() == _current(home, "b").resolve()
    assert "a" in capsys.readouterr().err


def test_relink_is_noop_when_symlink_already_correct(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    before = _history(home, "w").read_text()

    rc = relink.main([])
    assert rc == 0

    assert _history(home, "w").read_text() == before


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

    assert link.resolve() == _current(home, "w").resolve()


def test_relink_handles_multiple_skills(home, fake_upstream_repo):
    _install_ab(home, fake_upstream_repo)

    skills_dir = home / ".claude" / "skills"
    (skills_dir / "a").unlink()
    (skills_dir / "b").unlink()

    rc = relink.main([])
    assert rc == 0

    assert (skills_dir / "a").resolve() == _current(home, "a").resolve()
    assert (skills_dir / "b").resolve() == _current(home, "b").resolve()
