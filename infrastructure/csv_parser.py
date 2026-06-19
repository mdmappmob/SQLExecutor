import csv
import os
from dataclasses import dataclass, field
from typing import Optional

from infrastructure.i18n import I18N


@dataclass
class CsvProfile:
    delimiter: str = ","
    has_header: bool = True
    encoding: str = "utf-8-sig"
    columns: list[str] = field(default_factory=list)
    sample_rows: list[list[str]] = field(default_factory=list)
    total_rows: int = 0
    file_path: str = ""


@dataclass
class BatchInsert:
    sql_template: str = ""
    params: list[list[str | None]] = field(default_factory=list)
    table: str = ""
    batch_size: int = 1000


class CsvParser:
    _delimiters = [",", ";", "\t", "|"]

    @classmethod
    def detect_delimiter(cls, first_line: str) -> str:
        counts = {d: first_line.count(d) for d in cls._delimiters}
        best = max(counts, key=counts.get) if max(counts.values()) > 0 else ","
        return best

    @classmethod
    def profile(
        cls,
        file_path: str,
        has_header: bool = True,
        encoding: Optional[str] = None,
    ) -> CsvProfile:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(I18N.infrastructure["file_not_found"].format(path=file_path))

        if encoding is None:
            encoding = cls._detect_encoding(file_path)

        with open(file_path, "r", encoding=encoding) as f:
            first_line = f.readline()

        delimiter = cls.detect_delimiter(first_line)

        with open(file_path, "r", encoding=encoding) as f:
            rows = list(csv.reader(f, delimiter=delimiter))

        if not rows:
            raise ValueError("CSV file is empty")

        columns = (
            rows[0]
            if has_header
            else [str(i + 1) for i in range(len(rows[0]))]
        )
        data_rows = rows[1:] if has_header else rows

        if not data_rows:
            raise ValueError("CSV file has no data rows (only header)")

        return CsvProfile(
            delimiter=delimiter,
            has_header=has_header,
            encoding=encoding,
            columns=columns,
            sample_rows=data_rows[:10],
            total_rows=len(data_rows),
            file_path=file_path,
        )

    @staticmethod
    def _detect_encoding(file_path: str) -> str:
        with open(file_path, "rb") as f:
            raw = f.read(4)
        if raw[:3] == b"\xef\xbb\xbf":
            return "utf-8-sig"
        if raw[:2] == b"\xff\xfe":
            return "utf-16-le"
        if raw[:2] == b"\xfe\xff":
            return "utf-16-be"
        return "utf-8"

    @classmethod
    def prepare_insert(
        cls,
        file_path: str,
        table: str,
        column_mapping: dict[str, str],
        has_header: bool = True,
        encoding: str = "utf-8-sig",
        batch_size: int = 1000,
    ) -> BatchInsert:
        with open(file_path, "r", encoding=encoding) as f:
            first_line = f.readline()
        delimiter = cls.detect_delimiter(first_line)

        with open(file_path, "r", encoding=encoding) as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader) if has_header else None

            source_keys = list(column_mapping.keys())
            target_cols = list(column_mapping.values())

            col_indices: list[int] = []
            for key in source_keys:
                if has_header and header:
                    col_indices.append(header.index(key))
                else:
                    col_indices.append(int(key) - 1)

            placeholders = ", ".join("?" for _ in target_cols)
            col_names = ", ".join(f"[{c}]" for c in target_cols)
            sql_template = f"INSERT INTO [{table}] ({col_names}) VALUES ({placeholders})"

            all_params: list[list[object]] = []
            for row in reader:
                if not row or all(c.strip() == "" for c in row):
                    continue
                vals: list[object] = []
                for i in col_indices:
                    raw = row[i].strip() if i < len(row) else ""
                    vals.append(None if raw.upper() == "NULL" else raw)
                all_params.append(vals)

        return BatchInsert(
            sql_template=sql_template,
            params=all_params,
            table=table,
            batch_size=batch_size,
        )
