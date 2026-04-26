import json
from pathlib import Path

from scripts import install


def test_install_seeds_three_trees_and_symlink_and_registry(home, fake_upstream_repo, capsys):
    repo_url = fake_upstream_repo(
        "acme/widget",
        "skills/widget",
        {"SKILL.md": "---\nname: widget\n---\n# v1\n", "helper.py": "x = 1\n"},
    )

    rc = install.main(["widget", repo_url, "skills/widget"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "widget"
    for layer in ("active", "baseline", "upstream"):
        assert (base / layer / "SKILL.md").read_text() == "---\nname: widget\n---\n# v1\n"
        assert (base / layer / "helper.py").read_text() == "x = 1\n"

    symlink = home / ".claude" / "skills" / "widget"
    assert symlink.is_symlink()
    assert symlink.resolve() == (base / "active").resolve()

    registry = json.loads((home / ".agents" / "sync-skills" / "sources.json").read_text())
    assert registry == {"widget": {"repo": repo_url, "path": "skills/widget", "ref": "HEAD"}}

    history = (home / ".agents" / "sync-skills" / "history.log").read_text().strip().splitlines()
    assert len(history) == 1
    assert "install" in history[0] and "widget" in history[0]
