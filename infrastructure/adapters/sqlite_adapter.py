import re
import sqlite3
import time

from domain.entities import ExecutionResult, ProcedureInfo, SequenceInfo, TriggerInfo, ViewInfo
from domain.interfaces import ColumnInfo, DatabaseAdapter, ForeignKeyInfo, IndexInfo, TableInfo
from domain.value_objects import ConnectionConfig, SQLText
from infrastructure.i18n import I18N


class SQLiteAdapter(DatabaseAdapter):
    _connection: sqlite3.Connection | None = None
    _server: str = ""
    _database: str = ""

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        self._connection = sqlite3.connect(config.database.value)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            finally:
                self._connection = None

    def is_connected(self) -> bool:
        if self._connection is None:
            return False
        try:
            cursor = self._connection.execute("SELECT 1")
            cursor.close()
            return True
        except sqlite3.Error:
            return False

    def execute(self, sql: SQLText) -> ExecutionResult:
        if not self._connection:
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=0,
                message=I18N.infrastructure["not_connected"]
            )

        start = time.perf_counter()
        sql_text = sql.value.strip()

        try:
            cursor = self._connection.execute(sql_text)
            if cursor.description:
                rows = [list(row) for row in cursor.fetchall()]
                columns = [desc[0] for desc in cursor.description]
                duration_ms = int((time.perf_counter() - start) * 1000)
                return ExecutionResult(
                    success=True, rows_affected=len(rows),
                    duration_ms=duration_ms,
                    message=I18N.infrastructure["rows_returned"].format(n=len(rows)),
                    columns=columns, rows=rows
                )
            else:
                self._connection.commit()
                rows_affected = cursor.rowcount
                duration_ms = int((time.perf_counter() - start) * 1000)
                return ExecutionResult(
                    success=True, rows_affected=rows_affected,
                    duration_ms=duration_ms,
                    message=I18N.infrastructure["rows_affected"].format(n=rows_affected)
                )
        except sqlite3.Error as e:
            self._connection.rollback()
            duration_ms = int((time.perf_counter() - start) * 1000)
            error_msg = str(e).strip()
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=duration_ms,
                message=I18N.infrastructure["error"].format(msg=error_msg)
            )

    def executemany(self, sql_template: str, params: list[list]) -> ExecutionResult:
        if not self._connection:
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=0,
                message=I18N.infrastructure["not_connected"]
            )

        start = time.perf_counter()
        total = len(params)
        successful = 0
        failed = 0
        last_error = ""

        for row in params:
            try:
                self._connection.execute(sql_template, row)
                self._connection.commit()
                successful += 1
            except sqlite3.Error as e:
                self._connection.rollback()
                failed += 1
                if not last_error:
                    last_error = str(e)[:300]

        duration_ms = int((time.perf_counter() - start) * 1000)

        if failed == 0:
            return ExecutionResult(
                success=True, rows_affected=successful,
                duration_ms=duration_ms,
                message=I18N.infrastructure["rows_inserted"].format(n=successful)
            )
        else:
            return ExecutionResult(
                success=successful > 0, rows_affected=successful,
                duration_ms=duration_ms,
                message=(f"{successful} inserido(s), {failed} erro(s). "
                         f"Primeiro erro: {last_error}")
            )

    def get_schema(self) -> list[TableInfo]:
        tables: list[TableInfo] = []
        if not self._connection:
            return tables
        cursor = self._connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
        )
        for row in cursor.fetchall():
            tname, ttype = row[0], row[1]
            type_label = "VIEW" if ttype == "view" else "TABLE"

            columns: list[ColumnInfo] = []
            for c in self._connection.execute(f"PRAGMA table_info({self._quote(tname)})"):
                cid, name, dtype, notnull, dflt, pk = c
                columns.append(ColumnInfo(
                    name=name,
                    data_type=dtype,
                    nullable=not notnull,
                    is_pk=bool(pk),
                    default_value=dflt,
                ))

            foreign_keys: list[ForeignKeyInfo] = []
            if type_label == "TABLE":
                for fk in self._connection.execute(f"PRAGMA foreign_key_list({self._quote(tname)})"):
                    fk_id, seq, ref_table, fk_from, fk_to, on_upd, on_del, match = fk
                    foreign_keys.append(ForeignKeyInfo(
                        column=fk_from,
                        ref_table=ref_table,
                        ref_column=fk_to,
                        fk_name=str(fk_id),
                    ))

            indexes: list[IndexInfo] = []
            if type_label == "TABLE":
                for ix in self._connection.execute(f"PRAGMA index_list({self._quote(tname)})"):
                    seq, iname, iunique, origin, partial = ix
                    icols: list[str] = []
                    for ix_col in self._connection.execute(f"PRAGMA index_info({self._quote(iname)})"):
                        seqno, cid, col_name = ix_col
                        if col_name is not None:
                            icols.append(col_name)
                    indexes.append(IndexInfo(
                        name=iname,
                        columns=icols,
                        is_unique=bool(iunique),
                    ))

            tables.append(TableInfo(
                name=tname,
                type=type_label,
                columns=columns,
                foreign_keys=foreign_keys,
                indexes=indexes,
            ))

        return tables

    def get_table_columns(self, table_name: str, schema: str | None = None) -> list[ColumnInfo]:
        result: list[ColumnInfo] = []
        if not self._connection:
            return result
        for row in self._connection.execute(f"PRAGMA table_info({self._quote(table_name)})"):
            cid, name, dtype, notnull, dflt, pk = row
            result.append(ColumnInfo(
                name=name,
                data_type=dtype,
                nullable=not notnull,
                is_pk=bool(pk),
                default_value=dflt,
            ))
        return result

    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]:
        conn = None
        try:
            conn = sqlite3.connect(config.database.value)
            conn.execute("SELECT 1")
            return True, ""
        except sqlite3.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_sequences(self) -> list[SequenceInfo]:
        return []

    def get_views(self) -> list[ViewInfo]:
        result: list[ViewInfo] = []
        if not self._connection:
            return result
        for row in self._connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='view'"
        ):
            result.append(ViewInfo(name=row[0], definition=row[1] or ""))
        return result

    def get_triggers(self) -> list[TriggerInfo]:
        result: list[TriggerInfo] = []
        if not self._connection:
            return result
        for row in self._connection.execute(
            "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger'"
        ):
            name, tbl_name, sql_text = row[0], row[1], row[2] or ""
            event = self._parse_trigger_event(sql_text)
            result.append(TriggerInfo(name=name, event=event, table_name=tbl_name, body=sql_text))
        return result

    def get_procedures(self) -> list[ProcedureInfo]:
        return []

    def execute_autocommit(self, sql: SQLText) -> ExecutionResult:
        return self.execute(sql)

    def _quote(self, name: str) -> str:
        return '"' + name + '"'

    @staticmethod
    def _parse_trigger_event(sql_text: str) -> str:
        m = re.search(
            r'(BEFORE|AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE)',
            sql_text,
            re.IGNORECASE,
        )
        if m:
            timing = m.group(1).upper()
            event = m.group(2).upper()
            if timing == "INSTEAD OF":
                return f"INSTEAD OF {event}"
            return f"{timing} {event}"
        return ""
