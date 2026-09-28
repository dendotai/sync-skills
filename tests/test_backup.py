from sync_skills import backup_current, paths_for


def test_bak_created_when_absent(home):
    current = paths_for("w").current
    current.mkdir(parents=True)
    (current / "SKILL.md").write_text("v1\n")

    bak = backup_current("w")

    assert bak == current / "SKILL.md.bak"
    assert bak.read_text() == "v1\n"


def test_bak_overwrites_existing(home):
    current = paths_for("w").current
    current.mkdir(parents=True)
    (current / "SKILL.md").write_text("now\n")
    (current / "SKILL.md.bak").write_text("stale\n")

    backup_current("w")

    assert (current / "SKILL.md.bak").read_text() == "now\n"


def test_bak_leaves_original_untouched(home):
    current = paths_for("w").current
    current.mkdir(parents=True)
    (current / "SKILL.md").write_text("the original\n")

    backup_current("w")

    assert (current / "SKILL.md").read_text() == "the original\n"
