import time

import psycopg2

from domain.interfaces import DatabaseAdapter
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult
from infrastructure.i18n import I18N


class PostgreSQLAdapter(DatabaseAdapter):
    _connection: psycopg2.extensions.connection | None = None
    _server: str = ""
    _database: str = ""

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        self._connection = psycopg2.connect(
            host=config.server.value,
            port=config.port,
            dbname=config.database.value,
            user=config.username,
            password=config.password,
            connect_timeout=config.timeout_seconds,
        )
        self._connection.autocommit = False

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
        except psycopg2.Error:
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
        except psycopg2.Error as e:
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
            except psycopg2.Error as e:
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
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_name
            """)
            for row in cursor.fetchall():
                tname, ttype_raw = row[0], row[1]
                type_label = "VIEW" if ttype_raw == "VIEW" else "TABLE"
                columns: list[ColumnInfo] = []
                cursor.execute("""
                    SELECT c.column_name, c.data_type,
                           CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                           CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    WHERE c.table_name = %s
                      AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY c.ordinal_position
                """, (tname, tname))
                for c in cursor.fetchall():
                    columns.append(ColumnInfo(name=c[0], data_type=c[1], nullable=bool(c[2]), is_pk=bool(c[3])))
                foreign_keys: list[ForeignKeyInfo] = []
                indexes: list[IndexInfo] = []
                if type_label == "TABLE":
                    try:
                        cursor.execute("""
                            SELECT
                                ku.column_name,
                                ref_ku.table_name,
                                ref_ku.column_name,
                                tc.constraint_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage ku
                                ON tc.constraint_name = ku.constraint_name
                            JOIN information_schema.referential_constraints rc
                                ON tc.constraint_name = rc.constraint_name
                            JOIN information_schema.key_column_usage ref_ku
                                ON rc.unique_constraint_name = ref_ku.constraint_name
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                              AND tc.table_name = %s
                        """, (tname,))
                        for fk in cursor.fetchall():
                            foreign_keys.append(ForeignKeyInfo(column=fk[0], ref_table=fk[1], ref_column=fk[2], fk_name=fk[3]))
                    except Exception:
                        pass
                    try:
                        cursor.execute("""
                            SELECT indexname, indexdef
                            FROM pg_indexes
                            WHERE tablename = %s
                              AND indexname NOT LIKE '%_pkey'
                            ORDER BY indexname
                        """, (tname,))
                        for ix in cursor.fetchall():
                            idx_name = ix[0]
                            idx_def = ix[1]
                            is_unique = "UNIQUE" in idx_def
                            cols_part = idx_def.split("(")[-1].rstrip(")") if "(" in idx_def else ""
                            idx_cols = [c.strip().strip('"') for c in cols_part.split(",")] if cols_part else []
                            indexes.append(IndexInfo(name=idx_name, columns=idx_cols, is_unique=is_unique))
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
            if schema:
                cursor.execute("""
                    SELECT c.column_name, c.data_type,
                           CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                           CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    WHERE c.table_name = %s
                      AND c.table_schema = %s
                    ORDER BY c.ordinal_position
                """, (table_name, table_name, schema))
            else:
                cursor.execute("""
                    SELECT c.column_name, c.data_type,
                           CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                           CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    WHERE c.table_name = %s
                      AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY c.ordinal_position
                """, (table_name, table_name))
            for row in cursor.fetchall():
                result.append(ColumnInfo(name=row[0], data_type=row[1], nullable=bool(row[2]), is_pk=bool(row[3])))
        finally:
            cursor.close()
        return result

    def test_connection(self, config: ConnectionConfig) -> bool:
        conn = None
        try:
            conn = psycopg2.connect(
                host=config.server.value,
                port=config.port,
                dbname=config.database.value,
                user=config.username,
                password=config.password,
                connect_timeout=10,
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except psycopg2.Error:
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
