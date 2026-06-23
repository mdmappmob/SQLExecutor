import json
import os
from pathlib import Path


_SESSION_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "config" / "session.json"
_SESSION_FILE = _SESSION_FILE.resolve()


def save_session(data: dict):
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_session() -> dict:
    if not _SESSION_FILE.exists():
        return {}
    try:
        with open(_SESSION_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
