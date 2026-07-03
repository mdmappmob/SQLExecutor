import time

import pymysql

from domain.interfaces import DatabaseAdapter
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult
from infrastructure.i18n import I18N


class MySQLAdapter(DatabaseAdapter):
    _connection: pymysql.Connection | None = None
    _server: str = ""
    _database: str = ""

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        kwargs = {
            "host": config.server.value,
            "database": config.database.value,
            "user": config.username,
            "password": config.password,
            "connect_timeout": config.timeout_seconds,
            "autocommit": False,
        }
        if config.port:
            kwargs["port"] = config.port
        self._connection = pymysql.connect(**kwargs)

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
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except pymysql.Error:
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
        except pymysql.Error as e:
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
            except pymysql.Error as e:
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
        from domain.interfaces import TableInfo, ColumnInfo, ForeignKeyInfo, IndexInfo
        tables: list[TableInfo] = []
        if not self._connection:
            return tables
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT TABLE_NAME, TABLE_TYPE
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                ORDER BY TABLE_NAME
            """)
            for row in cursor.fetchall():
                tname, ttype_raw = row[0], row[1]
                type_label = "VIEW" if ttype_raw == "VIEW" else "TABLE"
                columns: list[ColumnInfo] = []
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE,
                           CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END,
                           CASE WHEN COLUMN_KEY = 'PRI' THEN 1 ELSE 0 END
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """, (tname,))
                for c in cursor.fetchall():
                    columns.append(ColumnInfo(name=c[0], data_type=c[1], nullable=bool(c[2]), is_pk=bool(c[3])))
                foreign_keys: list[ForeignKeyInfo] = []
                indexes: list[IndexInfo] = []
                if type_label == "TABLE":
                    try:
                        cursor.execute("""
                            SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, CONSTRAINT_NAME
                            FROM information_schema.KEY_COLUMN_USAGE
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = %s
                              AND REFERENCED_TABLE_NAME IS NOT NULL
                        """, (tname,))
                        for fk in cursor.fetchall():
                            foreign_keys.append(ForeignKeyInfo(column=fk[0], ref_table=fk[1], ref_column=fk[2], fk_name=fk[3]))
                    except Exception:
                        pass
                    try:
                        cursor.execute("""
                            SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX
                            FROM information_schema.STATISTICS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = %s
                              AND INDEX_NAME != 'PRIMARY'
                            ORDER BY INDEX_NAME, SEQ_IN_INDEX
                        """, (tname,))
                        idx_map: dict[str, tuple[list[str], bool]] = {}
                        for ix in cursor.fetchall():
                            iname = ix[0]
                            if iname not in idx_map:
                                idx_map[iname] = ([], ix[2] == 0)
                            idx_map[iname][0].append(ix[1])
                        for iname, (icols, iunique) in idx_map.items():
                            indexes.append(IndexInfo(name=iname, columns=icols, is_unique=iunique))
                    except Exception:
                        pass
                tables.append(TableInfo(name=tname, type=type_label, columns=columns, foreign_keys=foreign_keys, indexes=indexes))
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
                SELECT COLUMN_NAME, DATA_TYPE,
                       CASE WHEN IS_NULLABLE = 'YES' THEN 1 ELSE 0 END,
                       CASE WHEN COLUMN_KEY = 'PRI' THEN 1 ELSE 0 END
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (table_name,))
            for row in cursor.fetchall():
                result.append(ColumnInfo(name=row[0], data_type=row[1], nullable=bool(row[2]), is_pk=bool(row[3])))
        finally:
            cursor.close()
        return result

    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]:
        conn = None
        try:
            kwargs = {
                "host": config.server.value,
                "database": config.database.value,
                "user": config.username,
                "password": config.password,
                "connect_timeout": 10,
            }
            if config.port:
                kwargs["port"] = config.port
            conn = pymysql.connect(**kwargs)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True, ""
        except pymysql.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
