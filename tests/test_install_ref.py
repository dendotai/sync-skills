import subprocess
from pathlib import Path

from scripts import install


def test_install_with_explicit_ref_checks_out_that_ref(home, fake_upstream_repo):
    repo_url = fake_upstream_repo(
        "acme/widget",
        "skills/widget",
        {"SKILL.md": "v1\n"},
    )
    repo_dir = Path(repo_url.removeprefix("file://"))
    subprocess.run(["git", "checkout", "-q", "-b", "v2"], cwd=repo_dir, check=True)
    (repo_dir / "skills" / "widget" / "SKILL.md").write_text("v2\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "v2"], cwd=repo_dir, check=True)

    rc = install.main(["widget", repo_url, "skills/widget", "v2"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "widget"
    assert (base / "active" / "SKILL.md").read_text() == "v2\n"
    assert (base / "baseline" / "SKILL.md").read_text() == "v2\n"
    assert (base / "upstream" / "SKILL.md").read_text() == "v2\n"
