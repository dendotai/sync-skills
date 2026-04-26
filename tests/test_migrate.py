import json

import migrate


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
        "sourceUrl": f"https://github.com/{source}.git",
        "skillPath": skill_path,
        "skillFolderHash": hash_,
        "installedAt": "2026-04-01T00:00:00.000Z",
        "updatedAt": "2026-04-01T00:00:00.000Z",
    }
    lock.write_text(json.dumps(data))


def test_migrate_named_skill_populates_three_trees_and_symlink_and_registry(home):
    _seed_npx(
        home,
        "widget",
        "skills/widget/SKILL.md",
        "acme/skills",
        "abc123",
        {"SKILL.md": "---\nname: widget\n---\n# v1\n", "helper.py": "x = 1\n"},
    )

    rc = migrate.main(["widget"])
    assert rc == 0

    base = home / ".agents" / "sync-skills" / "widget"
    for layer in ("active", "baseline", "upstream"):
        assert (base / layer / "SKILL.md").read_text() == "---\nname: widget\n---\n# v1\n"
        assert (base / layer / "helper.py").read_text() == "x = 1\n"

    symlink = home / ".claude" / "skills" / "widget"
    assert symlink.is_symlink()
    assert symlink.resolve() == (base / "active").resolve()

    registry = json.loads((home / ".agents" / "sync-skills" / "sources.json").read_text())
    assert registry == {
        "widget": {"repo": "acme/skills", "path": "skills/widget", "ref": "abc123"}
    }

    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert "widget" not in lock["skills"]

    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert len(history) == 1
    assert "migrate" in history[0] and "widget" in history[0]


def test_migrate_derives_path_for_flat_layout(home):
    # mattpocock/skills layout: skill at repo root, skillPath = "<name>/SKILL.md".
    _seed_npx(home, "tdd", "tdd/SKILL.md", "mattpocock/skills", "deadbeef", {"SKILL.md": "v\n"})

    migrate.main(["tdd"])

    registry = json.loads((home / ".agents" / "sync-skills" / "sources.json").read_text())
    assert registry["tdd"] == {
        "repo": "mattpocock/skills",
        "path": "tdd",
        "ref": "deadbeef",
    }


def test_migrate_is_noop_when_already_migrated(home):
    _seed_npx(home, "widget", "widget/SKILL.md", "x/skills", "h", {"SKILL.md": "v1\n"})
    migrate.main(["widget"])

    # User customizes active/ after migration; lock somehow still names it.
    base = home / ".agents" / "sync-skills" / "widget"
    (base / "active" / "SKILL.md").write_text("my custom\n")
    lock_path = home / ".agents" / ".skill-lock.json"
    lock = json.loads(lock_path.read_text())
    lock["skills"]["widget"] = {
        "source": "x/skills",
        "skillPath": "widget/SKILL.md",
        "skillFolderHash": "h",
    }
    lock_path.write_text(json.dumps(lock))

    rc = migrate.main(["widget"])
    assert rc == 0

    # Active untouched, no extra audit event, lock entry cleaned up.
    assert (base / "active" / "SKILL.md").read_text() == "my custom\n"
    history = (home / ".agents" / "sync-skills" / "history.log").read_text().splitlines()
    assert len(history) == 1
    lock = json.loads(lock_path.read_text())
    assert "widget" not in lock["skills"]


def test_migrate_replaces_preexisting_symlink_into_npx_skills(home):
    _seed_npx(home, "widget", "widget/SKILL.md", "x/skills", "h", {"SKILL.md": "v\n"})
    symlink = home / ".claude" / "skills" / "widget"
    symlink.symlink_to(home / ".agents" / "skills" / "widget")

    rc = migrate.main(["widget"])
    assert rc == 0

    expected = home / ".agents" / "sync-skills" / "widget" / "active"
    assert symlink.is_symlink()
    assert symlink.resolve() == expected.resolve()


def test_migrate_with_no_name_migrates_every_locked_skill(home):
    _seed_npx(home, "alpha", "alpha/SKILL.md", "x/skills", "h1", {"SKILL.md": "a\n"})
    _seed_npx(home, "beta", "beta/SKILL.md", "x/skills", "h2", {"SKILL.md": "b\n"})

    rc = migrate.main([])
    assert rc == 0

    base = home / ".agents" / "sync-skills"
    assert (base / "alpha" / "active" / "SKILL.md").read_text() == "a\n"
    assert (base / "beta" / "active" / "SKILL.md").read_text() == "b\n"

    registry = json.loads((base / "sources.json").read_text())
    assert set(registry.keys()) == {"alpha", "beta"}

    lock = json.loads((home / ".agents" / ".skill-lock.json").read_text())
    assert lock["skills"] == {}
