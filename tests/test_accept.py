import accept
import install


def test_accept_snaps_baseline_to_upstream(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    base = home / ".agents" / "sync-skills" / "w"
    (base / "upstream" / "SKILL.md").write_text("v2\n")

    rc = accept.main(["w"])
    assert rc == 0
    assert (base / "baseline" / "SKILL.md").read_text() == "v2\n"


def test_accept_appends_audit_event(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    accept.main(["w"])

    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert len(history) == 2
    assert "install" in history[0] and "w" in history[0]
    assert "accept" in history[1] and "w" in history[1]


def test_accept_handles_added_and_removed_files(home, fake_upstream_repo):
    repo_url = fake_upstream_repo(
        "acme/w", "skills/w", {"SKILL.md": "v1\n", "old.py": "old = 1\n"}
    )
    install.main(["w", repo_url, "skills/w"])

    base = home / ".agents" / "sync-skills" / "w"
    (base / "upstream" / "old.py").unlink()
    (base / "upstream" / "new.py").write_text("new = 1\n")

    accept.main(["w"])

    assert not (base / "baseline" / "old.py").exists()
    assert (base / "baseline" / "new.py").read_text() == "new = 1\n"


def test_accept_leaves_active_untouched(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "v1\n"})
    install.main(["w", repo_url, "skills/w"])

    base = home / ".agents" / "sync-skills" / "w"
    (base / "active" / "SKILL.md").write_text("my custom v1\n")
    (base / "active" / "my_helper.py").write_text("local = True\n")
    (base / "upstream" / "SKILL.md").write_text("v2\n")

    accept.main(["w"])

    assert (base / "active" / "SKILL.md").read_text() == "my custom v1\n"
    assert (base / "active" / "my_helper.py").read_text() == "local = True\n"
