import json
import subprocess
from pathlib import Path

import migrate


def _git(repo_url, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo_url.removeprefix("file://"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo_url, subpath, files, message):
    repo_dir = Path(repo_url.removeprefix("file://"))
    for rel, content in files.items():
        (repo_dir / subpath / rel).write_text(content)
    _git(repo_url, "add", "-A")
    _git(repo_url, "commit", "-q", "-m", message)


def _seed_npx(home, name, skill_path, source, hash_, files):
    """Lay down ~/.agents/skills/<name>/<files> and a .skill-lock.json entry."""
    skill_dir = home / ".agents" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = skill_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    lock = home / ".agents" / ".skill-lock.json"
    data = json.loads(lock.read_text()) if lock.exists() else {"version": 3, "skills": {}}
    data["skills"][name] = {
        "source": source,
        "sourceType": "github",
        "sourceUrl": f"{source}.git",
        "skillPath": skill_path,
        "skillFolderHash": hash_,
        "installedAt": "2026-04-01T00:00:00.000Z",
        "updatedAt": "2026-04-01T00:00:00.000Z",
    }
    lock.write_text(json.dumps(data))


def _base(home, name):
    return home / ".agents" / "sync-skills" / "skills" / name


def test_migrate_copies_local_into_current_and_upstream_match_into_baseline(
    home, fake_upstream_repo
):
    repo = fake_upstream_repo("acme/skills", "skills/widget", {"SKILL.md": "v1\n"})
    tree = _git(repo, "rev-parse", "HEAD:skills/widget")
    head = _git(repo, "rev-parse", "HEAD")
    _seed_npx(
        home, "widget", "skills/widget/SKILL.md", repo, tree, {"SKILL.md": "v1 edited\n"}
    )

    rc = migrate.main(["widget"])
    assert rc == 0

    base = _base(home, "widget")
    assert (base / "current" / "SKILL.md").read_text() == "v1 edited\n"
    assert (base / "baseline" / "SKILL.md").read_text() == "v1\n"

    symlink = home / ".claude" / "skills" / "widget"
    assert symlink.is_symlink()
    assert symlink.resolve() == (base / "current").resolve()

    source = json.loads((base / "source.json").read_text())
    assert source == {"repo": repo, "path": "skills/widget", "commit": head}

    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert "widget" not in lock["skills"]

    history = (base / "history.log").read_text().splitlines()
    assert len(history) == 1
    assert history[0].split("\t")[1] == "migrate"


def test_migrate_picks_newest_commit_whose_folder_matches_the_lock_hash(
    home, fake_upstream_repo
):
    repo = fake_upstream_repo("acme/skills", "skills/widget", {"SKILL.md": "v1\n"})
    _commit(repo, "skills/widget", {"SKILL.md": "v2\n"}, "v2")
    v2 = _git(repo, "rev-parse", "HEAD")
    tree_v2 = _git(repo, "rev-parse", "HEAD:skills/widget")
    _commit(repo, "skills", {"OTHER.md": "unrelated\n"}, "touch another folder")
    after = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "skills/widget", {"SKILL.md": "v3\n"}, "v3")
    _seed_npx(home, "widget", "skills/widget/SKILL.md", repo, tree_v2, {"SKILL.md": "v2\n"})

    migrate.main(["widget"])

    base = _base(home, "widget")
    assert (base / "baseline" / "SKILL.md").read_text() == "v2\n"
    source = json.loads((base / "source.json").read_text())
    assert source["commit"] == after
    assert source["commit"] != v2


def test_migrate_without_matching_commit_uses_local_folder_as_baseline(
    home, fake_upstream_repo
):
    repo = fake_upstream_repo("acme/skills", "skills/widget", {"SKILL.md": "v1\n"})
    _seed_npx(
        home, "widget", "skills/widget/SKILL.md", repo, "0" * 40, {"SKILL.md": "local\n"}
    )

    rc = migrate.main(["widget"])
    assert rc == 0

    base = _base(home, "widget")
    assert (base / "current" / "SKILL.md").read_text() == "local\n"
    assert (base / "baseline" / "SKILL.md").read_text() == "local\n"
    source = json.loads((base / "source.json").read_text())
    assert source == {"repo": repo, "path": "skills/widget", "commit": None}


def test_migrate_derives_path_for_flat_layout(home, fake_upstream_repo):
    # mattpocock/skills layout: skill at repo root, skillPath = "<name>/SKILL.md".
    repo = fake_upstream_repo("mattpocock/skills", "tdd", {"SKILL.md": "v\n"})
    tree = _git(repo, "rev-parse", "HEAD:tdd")
    _seed_npx(home, "tdd", "tdd/SKILL.md", repo, tree, {"SKILL.md": "v\n"})

    migrate.main(["tdd"])

    source = json.loads((_base(home, "tdd") / "source.json").read_text())
    assert source["path"] == "tdd"
    assert source["commit"] == _git(repo, "rev-parse", "HEAD")


def test_migrate_is_noop_when_already_migrated(home, fake_upstream_repo):
    repo = fake_upstream_repo("x/skills", "widget", {"SKILL.md": "v1\n"})
    tree = _git(repo, "rev-parse", "HEAD:widget")
    _seed_npx(home, "widget", "widget/SKILL.md", repo, tree, {"SKILL.md": "v1\n"})
    migrate.main(["widget"])

    # User customizes current/ after migration; lock somehow still names it.
    base = _base(home, "widget")
    (base / "current" / "SKILL.md").write_text("my custom\n")
    _seed_npx(home, "widget", "widget/SKILL.md", repo, tree, {"SKILL.md": "v1\n"})

    rc = migrate.main(["widget"])
    assert rc == 0

    # current/ untouched, no extra log line, lock entry cleaned up.
    assert (base / "current" / "SKILL.md").read_text() == "my custom\n"
    assert len((base / "history.log").read_text().splitlines()) == 1
    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert "widget" not in lock["skills"]


def test_migrate_replaces_preexisting_symlink_into_npx_skills(home, fake_upstream_repo):
    repo = fake_upstream_repo("x/skills", "widget", {"SKILL.md": "v\n"})
    tree = _git(repo, "rev-parse", "HEAD:widget")
    _seed_npx(home, "widget", "widget/SKILL.md", repo, tree, {"SKILL.md": "v\n"})
    symlink = home / ".claude" / "skills" / "widget"
    symlink.symlink_to(home / ".agents" / "skills" / "widget")

    rc = migrate.main(["widget"])
    assert rc == 0

    assert symlink.is_symlink()
    assert symlink.resolve() == (_base(home, "widget") / "current").resolve()


def test_migrate_with_no_name_migrates_every_locked_skill(home, fake_upstream_repo):
    repo = fake_upstream_repo("x/skills", "alpha", {"SKILL.md": "a\n"})
    _seed_npx(home, "alpha", "alpha/SKILL.md", repo, "h1", {"SKILL.md": "a\n"})
    _seed_npx(home, "beta", "beta/SKILL.md", repo, "h2", {"SKILL.md": "b\n"})

    rc = migrate.main([])
    assert rc == 0

    assert (_base(home, "alpha") / "current" / "SKILL.md").read_text() == "a\n"
    assert (_base(home, "beta") / "current" / "SKILL.md").read_text() == "b\n"

    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert lock["skills"] == {}
