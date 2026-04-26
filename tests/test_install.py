import json
import subprocess
from pathlib import Path

import install


def test_install_seeds_three_trees_and_symlink_and_registry(home, fake_upstream_repo):
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


def test_install_with_explicit_ref(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/widget", "skills/widget", {"SKILL.md": "v1\n"})
    repo_dir = Path(repo_url.removeprefix("file://"))
    subprocess.run(["git", "checkout", "-q", "-b", "v2"], cwd=repo_dir, check=True)
    (repo_dir / "skills" / "widget" / "SKILL.md").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "v2"], cwd=repo_dir, check=True)

    rc = install.main(["widget", repo_url, "skills/widget", "v2"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "widget"
    for layer in ("active", "baseline", "upstream"):
        assert (base / layer / "SKILL.md").read_text() == "v2\n"


def test_install_refuses_existing_name(home, fake_upstream_repo, capsys):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    capsys.readouterr()

    rc = install.main(["w", repo_url, "skills/w"])
    assert rc != 0
    assert "already registered" in capsys.readouterr().err
