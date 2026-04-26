from scripts import install, list as list_script


def test_list_prints_registered_skills(home, fake_upstream_repo, capsys):
    repo_url = fake_upstream_repo("acme/widget", "skills/widget", {"SKILL.md": "x"})
    install.main(["widget", repo_url, "skills/widget"])
    capsys.readouterr()

    rc = list_script.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "widget" in out
    assert repo_url in out


def test_list_empty_when_no_skills(home, capsys):
    rc = list_script.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no skills" in out.lower() or out.strip() == ""
