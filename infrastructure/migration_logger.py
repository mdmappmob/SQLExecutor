import csv
import os
from datetime import datetime


class MigrationLogger:
    def __init__(self, log_dir: str = "logs"):
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def log(self, object_name: str, object_type: str, action: str, status: str, detail: str = "") -> None:
        filepath = os.path.join(self._log_dir, "migration_log.csv")
        row = {
            "timestamp": datetime.now().isoformat(),
            "object_name": object_name,
            "object_type": object_type,
            "action": action,
            "status": status,
            "detail": detail.replace("\r\n", " ").replace("\n", " "),
        }
        is_new = not os.path.isfile(filepath)
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def log_migration_start(self, source: str, target: str) -> None:
        self.log("MIGRATION", "META", "START", "INFO", f"Source={source}, Target={target}")

    def log_migration_end(self, ok: int, fail: int) -> None:
        self.log("MIGRATION", "META", "END", "INFO", f"OK={ok}, Fail={fail}")
