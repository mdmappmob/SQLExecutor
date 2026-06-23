import os
import sys
import time

_client_dir = (
    os.path.join(sys._MEIPASS, "infrastructure", "firebird_client")
    if getattr(sys, "frozen", False)
    else os.path.join(os.path.dirname(os.path.dirname(__file__)), "firebird_client")
)
if os.path.isdir(_client_dir):
    os.environ["PATH"] = _client_dir + os.pathsep + os.environ.get("PATH", "")

import fdb

from domain.interfaces import DatabaseAdapter
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult
from infrastructure.i18n import I18N


class FirebirdAdapter(DatabaseAdapter):
    _connection: fdb.Connection | None = None
    _server: str = ""
    _database: str = ""

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        dsn = config.database.value

        if config.use_windows_auth:
            self._connection = fdb.connect(dsn=dsn)
        else:
            self._connection = fdb.connect(
                dsn=dsn,
                user=config.username,
                password=config.password,
            )

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
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1 FROM RDB$DATABASE")
            cursor.close()
            return True
        except fdb.Error:
            return False

    def execute(self, sql: SQLText) -> ExecutionResult:
        if not self._connection:
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=0,
                message=I18N.infrastructure["not_connected"]
            )

        start = time.perf_counter()
        sql_text = sql.value.strip()
        cursor = self._connection.cursor()

        try:
            cursor.execute(sql_text)
            columns = [desc[0] for desc in cursor.description] if cursor.description else None
            if columns is not None:
                rows = [list(row) for row in cursor.fetchall()]
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
        except fdb.Error as e:
            self._connection.rollback()
            duration_ms = int((time.perf_counter() - start) * 1000)
            error_msg = str(e).strip()
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=duration_ms,
                message=I18N.infrastructure["error"].format(msg=error_msg)
            )
        finally:
            try:
                cursor.close()
            except Exception:
                pass

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
        cursor = self._connection.cursor()

        for row in params:
            try:
                cursor.execute(sql_template, row)
                self._connection.commit()
                successful += 1
            except fdb.Error as e:
                self._connection.rollback()
                failed += 1
                if not last_error:
                    last_error = str(e)[:300]

        cursor.close()
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
        from domain.interfaces import TableInfo, ColumnInfo
        tables: list[TableInfo] = []
        if not self._connection:
            return tables
        cursor = self._connection.cursor()
        try:
            for rel_type, type_label in [(0, "TABLE"), (1, "VIEW")]:
                cursor.execute("""
                    SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS
                    WHERE RDB$SYSTEM_FLAG = 0 AND RDB$RELATION_TYPE = ?
                    ORDER BY RDB$RELATION_NAME
                """, (rel_type,))
                for row in cursor.fetchall():
                    tname = row[0]
                    columns: list[ColumnInfo] = []
                    cursor.execute("""
                        SELECT
                            TRIM(RF.RDB$FIELD_NAME),
                            CASE F.RDB$FIELD_TYPE
                                WHEN 7 THEN 'SMALLINT' WHEN 8 THEN 'INTEGER'
                                WHEN 10 THEN 'FLOAT' WHEN 12 THEN 'DATE'
                                WHEN 13 THEN 'TIME' WHEN 14 THEN 'CHAR'
                                WHEN 16 THEN 'BIGINT' WHEN 27 THEN 'DOUBLE'
                                WHEN 35 THEN 'TIMESTAMP' WHEN 37 THEN 'VARCHAR'
                                WHEN 40 THEN 'CLOB' WHEN 45 THEN 'BLOB_ID'
                                WHEN 261 THEN 'BLOB' ELSE 'UNKNOWN'
                            END,
                            COALESCE(RF.RDB$NULL_FLAG, 0),
                            CASE WHEN pk.RDB$FIELD_NAME IS NOT NULL THEN 1 ELSE 0 END
                        FROM RDB$RELATION_FIELDS RF
                        JOIN RDB$FIELDS F ON RF.RDB$FIELD_SOURCE = F.RDB$FIELD_NAME
                        LEFT JOIN (
                            SELECT S.RDB$FIELD_NAME
                            FROM RDB$INDICES I
                            JOIN RDB$INDEX_SEGMENTS S ON I.RDB$INDEX_NAME = S.RDB$INDEX_NAME
                            WHERE I.RDB$RELATION_NAME = ?
                              AND I.RDB$UNIQUE_FLAG = 1
                              AND I.RDB$INDEX_INACTIVE IS NULL
                        ) pk ON pk.RDB$FIELD_NAME = RF.RDB$FIELD_NAME
                        WHERE RF.RDB$RELATION_NAME = ?
                        ORDER BY RF.RDB$FIELD_POSITION
                    """, (tname, tname))
                    for c in cursor.fetchall():
                        columns.append(ColumnInfo(name=c[0], data_type=c[1], nullable=not bool(c[2]), is_pk=bool(c[3])))
                    tables.append(TableInfo(name=tname, type=type_label, columns=columns))
        finally:
            cursor.close()
        return tables

    def get_table_columns(self, table_name: str, schema: str | None = None) -> list[ColumnInfo]:
        from domain.interfaces import ColumnInfo
        result: list[ColumnInfo] = []
        if not self._connection:
            return result
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT
                    TRIM(RF.RDB$FIELD_NAME),
                    CASE F.RDB$FIELD_TYPE
                        WHEN 7 THEN 'SMALLINT' WHEN 8 THEN 'INTEGER'
                        WHEN 10 THEN 'FLOAT' WHEN 12 THEN 'DATE'
                        WHEN 13 THEN 'TIME' WHEN 14 THEN 'CHAR'
                        WHEN 16 THEN 'BIGINT' WHEN 27 THEN 'DOUBLE'
                        WHEN 35 THEN 'TIMESTAMP' WHEN 37 THEN 'VARCHAR'
                        WHEN 40 THEN 'CLOB' WHEN 45 THEN 'BLOB_ID'
                        WHEN 261 THEN 'BLOB' ELSE 'UNKNOWN'
                    END,
                    COALESCE(RF.RDB$NULL_FLAG, 0),
                    CASE WHEN pk.RDB$FIELD_NAME IS NOT NULL THEN 1 ELSE 0 END
                FROM RDB$RELATION_FIELDS RF
                JOIN RDB$FIELDS F ON RF.RDB$FIELD_SOURCE = F.RDB$FIELD_NAME
                LEFT JOIN (
                    SELECT S.RDB$FIELD_NAME
                    FROM RDB$INDICES I
                    JOIN RDB$INDEX_SEGMENTS S ON I.RDB$INDEX_NAME = S.RDB$INDEX_NAME
                    WHERE I.RDB$RELATION_NAME = ?
                      AND I.RDB$UNIQUE_FLAG = 1
                      AND I.RDB$INDEX_INACTIVE IS NULL
                ) pk ON pk.RDB$FIELD_NAME = RF.RDB$FIELD_NAME
                WHERE RF.RDB$RELATION_NAME = ?
                ORDER BY RF.RDB$FIELD_POSITION
            """, (table_name, table_name))
            for row in cursor.fetchall():
                result.append(ColumnInfo(name=row[0], data_type=row[1], nullable=not bool(row[2]), is_pk=bool(row[3])))
        finally:
            cursor.close()
        return result

    def test_connection(self, config: ConnectionConfig) -> bool:
        conn = None
        try:
            dsn = config.database.value
            if config.use_windows_auth:
                conn = fdb.connect(dsn=dsn)
            else:
                conn = fdb.connect(
                    dsn=dsn,
                    user=config.username,
                    password=config.password,
                )
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM RDB$DATABASE")
            cursor.close()
            return True
        except fdb.Error:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
