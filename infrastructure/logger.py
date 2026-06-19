import csv
import os
from datetime import datetime

from domain.interfaces import AuditLogger


class CSVLogger(AuditLogger):
    _log_dir: str

    def __init__(self, log_dir: str = "logs"):
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _write_csv(self, filename: str, row: dict[str, str]) -> None:
        filepath = os.path.join(self._log_dir, filename)
        is_new = not os.path.isfile(filepath)
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def log_execution(self, sql: str, server: str, database: str, success: bool, rows: int, duration_ms: int) -> None:
        self._write_csv("query_log.csv", {
            "timestamp": datetime.now().isoformat(),
            "server": server,
            "database": database,
            "sql": sql.replace("\r\n", " ").replace("\n", " "),
            "success": str(success),
            "rows_affected": str(rows),
            "duration_ms": str(duration_ms),
        })

    def log_error(self, sql: str, server: str, database: str, error: str) -> None:
        self._write_csv("error_log.csv", {
            "timestamp": datetime.now().isoformat(),
            "server": server,
            "database": database,
            "sql": sql.replace("\r\n", " ").replace("\n", " "),
            "error": error.replace("\r\n", " ").replace("\n", " "),
        })

    def log_connection(self, server: str, database: str, success: bool) -> None:
        self._write_csv("connection_log.csv", {
            "timestamp": datetime.now().isoformat(),
            "server": server,
            "database": database,
            "success": str(success),
        })
