from scripts import install
from scripts.lib import layout


def test_is_clobbered_false_after_install(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    assert layout.is_clobbered("w") is False


def test_is_clobbered_true_when_symlink_points_outside_our_tree(home, fake_upstream_repo, tmp_path):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    p = layout.paths_for("w")
    p.symlink.unlink()
    p.symlink.symlink_to(foreign)
    assert layout.is_clobbered("w") is True


def test_is_clobbered_true_when_symlink_missing(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    layout.paths_for("w").symlink.unlink()
    assert layout.is_clobbered("w") is True


def test_exists_true_for_seeded_layers_false_otherwise(home, fake_upstream_repo):
    repo_url = fake_upstream_repo("acme/w", "skills/w", {"SKILL.md": "x"})
    install.main(["w", repo_url, "skills/w"])
    assert layout.exists("w", "active") is True
    assert layout.exists("w", "baseline") is True
    assert layout.exists("w", "upstream") is True
    assert layout.exists("missing", "active") is False
