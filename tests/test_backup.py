from core import backup_active, paths_for


def test_bak_created_when_absent(home):
    active = paths_for("w").active
    active.mkdir(parents=True)
    (active / "SKILL.md").write_text("v1\n")

    bak = backup_active("w")

    assert bak == active / "SKILL.md.bak"
    assert bak.read_text() == "v1\n"


def test_bak_overwrites_existing(home):
    active = paths_for("w").active
    active.mkdir(parents=True)
    (active / "SKILL.md").write_text("current\n")
    (active / "SKILL.md.bak").write_text("stale\n")

    backup_active("w")

    assert (active / "SKILL.md.bak").read_text() == "current\n"


def test_bak_leaves_original_untouched(home):
    active = paths_for("w").active
    active.mkdir(parents=True)
    (active / "SKILL.md").write_text("the original\n")

    backup_active("w")

    assert (active / "SKILL.md").read_text() == "the original\n"
