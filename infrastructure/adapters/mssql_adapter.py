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

    def execute_autocommit(self, sql: SQLText) -> ExecutionResult:
        if not self._connection:
            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=0,
                message=I18N.infrastructure["not_connected"]
            )
        old = self._connection.autocommit
        self._connection.autocommit = True
        try:
            return self.execute(sql)
        finally:
            self._connection.autocommit = old

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
        from domain.interfaces import TableInfo, ColumnInfo, ForeignKeyInfo, IndexInfo
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
                            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END,
                            c.COLUMN_DEFAULT,
                            COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity'),
                            c.CHARACTER_MAXIMUM_LENGTH,
                            c.NUMERIC_PRECISION,
                            c.NUMERIC_SCALE,
                            c.CHARACTER_SET_NAME,
                            c.COLLATION_NAME,
                            cc.DEFINITION,
                            ep.value AS comment
                        FROM INFORMATION_SCHEMA.COLUMNS c
                        LEFT JOIN (
                            SELECT ku.COLUMN_NAME
                            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                              AND tc.TABLE_NAME = ?
                        ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
                        LEFT JOIN INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
                            ON cc.CONSTRAINT_NAME = (
                                SELECT tc2.CONSTRAINT_NAME
                                FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                                WHERE ccu.TABLE_NAME = c.TABLE_NAME
                                  AND ccu.COLUMN_NAME = c.COLUMN_NAME
                                  AND ccu.CONSTRAINT_NAME IN (
                                      SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                                      WHERE CONSTRAINT_TYPE = 'CHECK' AND TABLE_NAME = c.TABLE_NAME
                                  )
                            )
                        LEFT JOIN sys.extended_properties ep
                            ON ep.major_id = OBJECT_ID(c.TABLE_NAME)
                            AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'ColumnId')
                            AND ep.name = 'MS_Description'
                        WHERE c.TABLE_NAME = ?
                        ORDER BY c.ORDINAL_POSITION
                    """, tname, tname)
                    for c in cursor.fetchall():
                        columns.append(ColumnInfo(
                            name=c[0], data_type=c[1],
                            nullable=bool(c[2]), is_pk=bool(c[3]),
                            default_value=c[4],
                            is_identity=bool(c[5]) if c[5] is not None else False,
                            char_length=c[6],
                            precision=c[7],
                            scale=c[8],
                            character_set=c[9] if c[9] else None,
                            collation=c[10] if c[10] else None,
                            check_constraint=c[11] if c[11] else None,
                            comment=c[12] if c[12] else None,
                        ))
                    foreign_keys: list[ForeignKeyInfo] = []
                    indexes: list[IndexInfo] = []
                    try:
                        cursor.execute("""
                            SELECT
                                ku.COLUMN_NAME,
                                ref_ku.TABLE_NAME,
                                ref_ku.COLUMN_NAME,
                                tc.CONSTRAINT_NAME
                            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                                ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ref_ku
                                ON rc.UNIQUE_CONSTRAINT_NAME = ref_ku.CONSTRAINT_NAME
                            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                              AND tc.TABLE_NAME = ?
                        """, tname)
                        for fk in cursor.fetchall():
                            foreign_keys.append(ForeignKeyInfo(column=fk[0], ref_table=fk[1], ref_column=fk[2], fk_name=fk[3]))
                    except Exception:
                        pass
                    try:
                        cursor.execute("""
                            SELECT i.name, col.name, i.is_unique, ic.key_ordinal
                            FROM sys.indexes i
                            JOIN sys.index_columns ic
                                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                            JOIN sys.columns col
                                ON ic.object_id = col.object_id AND ic.column_id = col.column_id
                            WHERE i.object_id = OBJECT_ID(?)
                            ORDER BY i.name, ic.key_ordinal
                        """, tname)
                        idx_map: dict[str, tuple[list[str], bool]] = {}
                        for ix in cursor.fetchall():
                            iname = ix[0]
                            if iname not in idx_map:
                                idx_map[iname] = ([], bool(ix[2]))
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
            if schema:
                cursor.execute("""
                    SELECT
                        c.COLUMN_NAME, c.DATA_TYPE,
                        CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END,
                        0,
                        c.COLUMN_DEFAULT,
                        COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity'),
                        c.CHARACTER_MAXIMUM_LENGTH,
                        c.NUMERIC_PRECISION,
                        c.NUMERIC_SCALE,
                        c.CHARACTER_SET_NAME,
                        c.COLLATION_NAME,
                        cc.DEFINITION,
                        ep.value AS comment
                    FROM INFORMATION_SCHEMA.COLUMNS c
                    LEFT JOIN INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
                        ON cc.CONSTRAINT_NAME = (
                            SELECT tc2.CONSTRAINT_NAME
                            FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                            WHERE ccu.TABLE_NAME = c.TABLE_NAME
                              AND ccu.COLUMN_NAME = c.COLUMN_NAME
                              AND ccu.CONSTRAINT_NAME IN (
                                  SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                                  WHERE CONSTRAINT_TYPE = 'CHECK' AND TABLE_NAME = c.TABLE_NAME
                              )
                        )
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = OBJECT_ID(c.TABLE_NAME)
                        AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'ColumnId')
                        AND ep.name = 'MS_Description'
                    WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
                    ORDER BY c.ORDINAL_POSITION
                """, schema, table_name)
            else:
                cursor.execute("""
                    SELECT
                        c.COLUMN_NAME, c.DATA_TYPE,
                        CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END,
                        0,
                        c.COLUMN_DEFAULT,
                        COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'IsIdentity'),
                        c.CHARACTER_MAXIMUM_LENGTH,
                        c.NUMERIC_PRECISION,
                        c.NUMERIC_SCALE,
                        c.CHARACTER_SET_NAME,
                        c.COLLATION_NAME,
                        cc.DEFINITION,
                        ep.value AS comment
                    FROM INFORMATION_SCHEMA.COLUMNS c
                    LEFT JOIN INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
                        ON cc.CONSTRAINT_NAME = (
                            SELECT tc2.CONSTRAINT_NAME
                            FROM INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu
                            WHERE ccu.TABLE_NAME = c.TABLE_NAME
                              AND ccu.COLUMN_NAME = c.COLUMN_NAME
                              AND ccu.CONSTRAINT_NAME IN (
                                  SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                                  WHERE CONSTRAINT_TYPE = 'CHECK' AND TABLE_NAME = c.TABLE_NAME
                              )
                        )
                    LEFT JOIN sys.extended_properties ep
                        ON ep.major_id = OBJECT_ID(c.TABLE_NAME)
                        AND ep.minor_id = COLUMNPROPERTY(OBJECT_ID(c.TABLE_NAME), c.COLUMN_NAME, 'ColumnId')
                        AND ep.name = 'MS_Description'
                    WHERE c.TABLE_NAME = ?
                    ORDER BY c.ORDINAL_POSITION
                """, table_name)
            for row in cursor.fetchall():
                result.append(ColumnInfo(
                    name=row[0], data_type=row[1],
                    nullable=bool(row[2]), is_pk=bool(row[3]),
                    default_value=row[4],
                    is_identity=bool(row[5]) if row[5] is not None else False,
                    char_length=row[6],
                    precision=row[7],
                    scale=row[8],
                    character_set=row[9] if row[9] else None,
                    collation=row[10] if row[10] else None,
                    check_constraint=row[11] if row[11] else None,
                    comment=row[12] if row[12] else None,
                ))
        finally:
            cursor.close()
        return result

    def get_sequences(self) -> list[SequenceInfo]:
        from domain.entities import SequenceInfo
        result: list[SequenceInfo] = []
        if not self._connection:
            return result
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT name, start_value, increment
                FROM sys.sequences
                ORDER BY name
            """)
            for row in cursor.fetchall():
                result.append(SequenceInfo(
                    name=row[0],
                    start_value=row[1] or 1,
                    increment=row[2] or 1,
                ))
        finally:
            cursor.close()
        return result

    def get_triggers(self) -> list[TriggerInfo]:
        from domain.entities import TriggerInfo
        result: list[TriggerInfo] = []
        if not self._connection:
            return result
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT
                    t.name,
                    OBJECT_NAME(t.parent_obj) AS table_name,
                    OBJECT_DEFINITION(t.object_id) AS definition
                FROM sys.triggers t
                WHERE t.parent_class_desc = 'OBJECT_OR_COLUMN'
                ORDER BY t.name
            """)
            for row in cursor.fetchall():
                result.append(TriggerInfo(
                    name=row[0],
                    event="",
                    body=row[2] or "",
                    table_name=row[1] or "",
                ))
        finally:
            cursor.close()
        return result

    def get_procedures(self) -> list[ProcedureInfo]:
        from domain.entities import ProcedureInfo
        result: list[ProcedureInfo] = []
        if not self._connection:
            return result
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT name, OBJECT_DEFINITION(object_id) AS definition
                FROM sys.procedures
                WHERE type = 'P'
                ORDER BY name
            """)
            for row in cursor.fetchall():
                result.append(ProcedureInfo(
                    name=row[0],
                    body=row[1] or "",
                    source=row[1] or "",
                ))
        finally:
            cursor.close()
        return result

    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]:
        conn = None
        try:
            conn_str = self._build_connection_string(config)
            conn = pyodbc.connect(conn_str, timeout=10)
            conn.execute("SELECT 1")
            return True, ""
        except pyodbc.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
