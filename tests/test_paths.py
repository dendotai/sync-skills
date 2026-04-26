from scripts import install, paths as paths_script


def test_paths_prints_four_paths(home, fake_upstream_repo, capsys):
    repo_url = fake_upstream_repo("acme/widget", "skills/widget", {"SKILL.md": "x"})
    install.main(["widget", repo_url, "skills/widget"])
    capsys.readouterr()

    rc = paths_script.main(["widget"])
    assert rc == 0
    out = capsys.readouterr().out

    base = str(home / ".agents" / "sync-skills" / "widget")
    assert f"{base}/active" in out
    assert f"{base}/baseline" in out
    assert f"{base}/upstream" in out
    assert str(home / ".claude" / "skills" / "widget") in out


def test_paths_unknown_skill_errors(home, capsys):
    rc = paths_script.main(["nope"])
    assert rc != 0
