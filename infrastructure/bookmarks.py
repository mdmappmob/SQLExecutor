import json
import os
from pathlib import Path


_BOOKMARKS_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "config" / "bookmarks.json"
_BOOKMARKS_FILE = _BOOKMARKS_FILE.resolve()


def save_bookmarks(bookmarks: list[dict]):
    _BOOKMARKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_BOOKMARKS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, indent=2, ensure_ascii=False)


def load_bookmarks() -> list[dict]:
    if not _BOOKMARKS_FILE.exists():
        return []
    try:
        with open(_BOOKMARKS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
