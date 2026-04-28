import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync_skills.py"


def test_audit_subcommand_appends_history_log(home):
    rc = subprocess.run(
        [sys.executable, str(SCRIPT), "audit", "cherry-pick", "widget"],
        check=False,
    ).returncode
    assert rc == 0

    log = home / ".agents" / "sync-skills" / "history.log"
    line = log.read_text().strip().splitlines()[-1]
    ts, action, skill = line.split("\t")
    assert action == "cherry-pick"
    assert skill == "widget"


def test_help_lists_audit_subcommand():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "audit" in result.stdout
