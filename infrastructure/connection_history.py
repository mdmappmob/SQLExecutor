import json
import os
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.config_manager import _get_config_dir


_SAFE_FIELDS = (
    "db_type",
    "server",
    "database",
    "username",
    "use_windows_auth",
    "port",
    "timeout",
)


def format_history_label(entry: dict) -> str:
    db_type = str(entry.get("db_type", "")).upper()
    server = str(entry.get("server", ""))
    database = str(entry.get("database", ""))
    username = str(entry.get("username", ""))
    if db_type in ("ORACLE", "FIREBIRD", "SQLITE") or not server:
        target = database
    else:
        target = f"{server}\\{database}"
    suffix = f" ({username})" if username else ""
    return f"[{db_type}] {target}{suffix}"


class ConnectionHistory:
    MAX_ENTRIES = 10

    def __init__(self, file_path: str | None = None):
        self._file_path = (
            Path(file_path)
            if file_path
            else _get_config_dir() / "connections_history.json"
        )

    def load(self) -> list[dict]:
        if not self._file_path.exists():
            return []
        try:
            with open(self._file_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            return [entry for entry in data if isinstance(entry, dict)]
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: list[dict]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._file_path)

    @staticmethod
    def _key(entry: dict) -> tuple:
        return (
            str(entry.get("db_type", "")).lower(),
            str(entry.get("server", "")).lower(),
            str(entry.get("database", "")).lower(),
            str(entry.get("username", "")).lower(),
            bool(entry.get("use_windows_auth", False)),
        )

    def _safe_entry(self, config: dict) -> dict:
        entry = {field: config.get(field) for field in _SAFE_FIELDS}
        entry["last_used"] = datetime.now(timezone.utc).isoformat()
        entry["uses"] = 1
        return entry

    def record(self, config: dict) -> list[dict]:
        entries = self.load()
        new_entry = self._safe_entry(config)
        new_key = self._key(new_entry)
        for i, entry in enumerate(entries):
            if self._key(entry) == new_key:
                existing = entries.pop(i)
                new_entry["uses"] = int(existing.get("uses", 1)) + 1
                entries.insert(0, new_entry)
                entries = entries[: self.MAX_ENTRIES]
                self._save(entries)
                return entries
        entries.insert(0, new_entry)
        entries = entries[: self.MAX_ENTRIES]
        self._save(entries)
        return entries

    def recent(self) -> list[dict]:
        return self.load()

    def clear(self) -> None:
        if self._file_path.exists():
            self._file_path.unlink(missing_ok=True)
