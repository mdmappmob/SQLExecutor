import time
from contextlib import contextmanager

import pyodbc

from domain.interfaces import DatabaseAdapter
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult
from infrastructure.i18n import I18N


class MSSQLAdapter(DatabaseAdapter):
    _connection: pyodbc.Connection | None = None
    _server: str = ""
    _database: str = ""
    _driver_name: str = ""

    @staticmethod
    def detect_best_driver() -> str:
        preferred = [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server",
        ]
        available = pyodbc.drivers()
        for name in preferred:
            if name in available:
                return name
        if available:
            return available[0]
        raise RuntimeError(I18N.infrastructure["driver_not_found"])

    def _build_connection_string(self, config: ConnectionConfig) -> str:
        if not self._driver_name:
            self._driver_name = self.detect_best_driver()

        base = (
            f"DRIVER={{{self._driver_name}}};"
            f"SERVER={config.server.value};"
            f"DATABASE={config.database.value};"
            f"Connection Timeout={config.timeout_seconds};"
        )
        if config.use_windows_auth:
            base += "Trusted_Connection=yes;"
        else:
            base += f"UID={config.username};PWD={config.password};"

        if "18" in self._driver_name or "17" in self._driver_name:
            base += f"Encrypt={'yes' if config.encrypt else 'no'};"
            base += f"TrustServerCertificate={'yes' if config.trust_server_certificate else 'no'};"
        return base

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        conn_str = self._build_connection_string(config)
        self._connection = pyodbc.connect(conn_str, autocommit=False)

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
            self._connection.execute("SELECT 1")
            return True
        except pyodbc.Error:
            return False

    @contextmanager
    def _transaction(self):
        cursor = self._connection.cursor()
        try:
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def execute(self, sql: SQLText) -> ExecutionResult:
        if not self._connection:
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=0,
                message=I18N.infrastructure["not_connected"]
            )

        start = time.perf_counter()
        sql_text = sql.value.strip()

        try:
            with self._transaction() as cursor:
                cursor.execute(sql_text)
                columns = [desc[0] for desc in cursor.description] if cursor.description else None
                if columns is not None:
                    rows = [list(row) for row in cursor.fetchall()]
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return ExecutionResult(
                        success=True, rows_affected=len(rows),
                        duration_ms=duration_ms, message=I18N.infrastructure["rows_returned"].format(n=len(rows)),
                        columns=columns, rows=rows
                    )
                else:
                    rows_affected = cursor.rowcount
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return ExecutionResult(
                        success=True, rows_affected=rows_affected,
                        duration_ms=duration_ms,
                        message=I18N.infrastructure["rows_affected"].format(n=rows_affected)
                    )
        except pyodbc.Error as e:
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
        cursor = self._connection.cursor()

        for row in params:
            try:
                cursor.execute(sql_template, row)
                self._connection.commit()
                successful += 1
            except pyodbc.Error as e:
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
            for table_type, type_label in [("BASE TABLE", "TABLE"), ("VIEW", "VIEW")]:
                cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = ? ORDER BY TABLE_NAME", table_type)
                for row in cursor.fetchall():
                    tname = row[0]
                    columns: list[ColumnInfo] = []
                    cursor.execute("""
                        SELECT
                            c.COLUMN_NAME, c.DATA_TYPE,
                            CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END,
                            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END
                        FROM INFORMATION_SCHEMA.COLUMNS c
                        LEFT JOIN (
                            SELECT ku.COLUMN_NAME
                            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                              AND tc.TABLE_NAME = ?
                        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
                        WHERE c.TABLE_NAME = ?
                        ORDER BY c.ORDINAL_POSITION
                    """, tname, tname)
                    for c in cursor.fetchall():
                        columns.append(ColumnInfo(name=c[0], data_type=c[1], nullable=bool(c[2]), is_pk=bool(c[3])))
                    tables.append(TableInfo(name=tname, type=type_label, columns=columns))
        finally:
            cursor.close()
        return tables

    def test_connection(self, config: ConnectionConfig) -> bool:
        conn = None
        try:
            conn_str = self._build_connection_string(config)
            conn = pyodbc.connect(conn_str, timeout=10)
            conn.execute("SELECT 1")
            return True
        except pyodbc.Error:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
