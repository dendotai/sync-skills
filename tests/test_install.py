import json
import subprocess
from pathlib import Path

import install


def _head(repo_url: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_url.removeprefix("file://"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_install_seeds_current_baseline_source_and_symlink(home, fake_upstream_repo):
    repo_url = fake_upstream_repo(
        "acme/widget",
        "skills/widget",
        {"SKILL.md": "---\nname: widget\n---\n# v1\n", "helper.py": "x = 1\n"},
    )

    rc = install.main(["widget", repo_url, "skills/widget"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "skills" / "widget"
    for layer in ("current", "baseline"):
        assert (base / layer / "SKILL.md").read_text() == "---\nname: widget\n---\n# v1\n"
        assert (base / layer / "helper.py").read_text() == "x = 1\n"
    assert sorted(p.name for p in base.iterdir()) == [
        "baseline",
        "current",
        "history.log",
        "source.json",
    ]

    symlink = home / ".claude" / "skills" / "widget"
    assert symlink.is_symlink()
    assert symlink.resolve() == (base / "current").resolve()

    source = json.loads((base / "source.json").read_text())
    assert source == {"repo": repo_url, "path": "skills/widget", "commit": _head(repo_url)}

    history = (base / "history.log").read_text().splitlines()
    assert len(history) == 1
    assert history[0].split("\t")[1] == "install"

    assert sorted(p.name for p in (home / ".agents" / "sync-skills").iterdir()) == ["skills"]


def test_install_with_explicit_ref(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/widget", "skills/widget", {"SKILL.md": "v1\n"})
    repo_dir = Path(repo_url.removeprefix("file://"))
    subprocess.run(["git", "checkout", "-q", "-b", "v2"], cwd=repo_dir, check=True)
    (repo_dir / "skills" / "widget" / "SKILL.md").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "v2"], cwd=repo_dir, check=True)

    rc = install.main(["widget", repo_url, "skills/widget", "v2"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "skills" / "widget"
    for layer in ("current", "baseline"):
        assert (base / layer / "SKILL.md").read_text() == "v2\n"
    source = json.loads((base / "source.json").read_text())
    assert source["commit"] == _head(repo_url)


def test_install_with_sha_ref(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/widget", "skills/widget", {"SKILL.md": "v1\n"})
    repo_dir = Path(repo_url.removeprefix("file://"))
    sha = _head(repo_url)
    (repo_dir / "skills" / "widget" / "SKILL.md").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "v2"], cwd=repo_dir, check=True)

    rc = install.main(["widget", repo_url, "skills/widget", sha])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "skills" / "widget"
    for layer in ("current", "baseline"):
        assert (base / layer / "SKILL.md").read_text() == "v1\n"
    assert json.loads((base / "source.json").read_text())["commit"] == sha


def test_install_refuses_existing_name(home, fake_upstream_repo, capsys):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    capsys.readouterr()

    rc = install.main(["w", repo_url, "skills/w"])
    assert rc != 0
    assert "already installed" in capsys.readouterr().err
