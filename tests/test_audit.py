import re

from scripts.lib import audit


def test_append_writes_iso_line(home):
    audit.append("install", "widget")
    log = home / ".agents" / "sync-skills" / "history.log"
    line = log.read_text().strip()
    parts = line.split("\t")
    assert len(parts) == 3
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", parts[0])
    assert parts[1] == "install"
    assert parts[2] == "widget"


def test_append_is_additive(home):
    audit.append("install", "a")
    audit.append("fetch", "a")
    audit.append("accept", "a")
    lines = (home / ".agents" / "sync-skills" / "history.log").read_text().strip().splitlines()
    assert [l.split("\t")[1] for l in lines] == ["install", "fetch", "accept"]
