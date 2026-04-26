from datetime import datetime, timezone

from .layout import root


def append(action: str, skill: str) -> None:
    log = root() / "history.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with log.open("a") as f:
        f.write(f"{ts}\t{action}\t{skill}\n")
