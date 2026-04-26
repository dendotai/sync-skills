from scripts.lib import registry


def test_set_and_get_round_trip(home):
    registry.set("widget", "acme/widget", "skills/widget", "main")
    assert registry.get("widget") == {"repo": "acme/widget", "path": "skills/widget", "ref": "main"}


def test_delete_removes_entry(home):
    registry.set("a", "x/y", ".", "HEAD")
    registry.set("b", "p/q", "skills/b", "HEAD")
    registry.delete("a")
    assert registry.get("a") is None
    assert registry.get("b") is not None


def test_delete_unknown_is_noop(home):
    registry.delete("nope")
    assert registry.load() == {}


def test_list_returns_sorted_names(home):
    registry.set("zebra", "x/y", ".")
    registry.set("apple", "p/q", ".")
    registry.set("mango", "m/n", ".")
    assert registry.list() == ["apple", "mango", "zebra"]
