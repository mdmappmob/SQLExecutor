import re
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
        return self._execute_with_retry(sql, retried=False)

    def _execute_with_retry(self, sql: SQLText, retried: bool) -> ExecutionResult:
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

            if not retried and 'does not exist' in error_msg:
                corrected_sql = self._auto_quote_table_names(sql_text, error_msg)
                if corrected_sql and corrected_sql != sql_text:
                    return self._execute_with_retry(SQLText(corrected_sql), retried=True)

            return ExecutionResult(
                success=False, rows_affected=0, duration_ms=duration_ms,
                message=I18N.infrastructure["error"].format(msg=error_msg)
            )
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def _auto_quote_table_names(self, sql_text: str, error_msg: str) -> str | None:
        m = re.search(r'relation "([^"]+)" does not exist', error_msg)
        if not m:
            return None
        ref = m.group(1)
        if not ref:
            return None
        if '.' in ref:
            schema_ref, table_ref = ref.split('.', 1)
        else:
            schema_ref, table_ref = None, ref
        try:
            cur = self._connection.cursor()
            if schema_ref:
                cur.execute(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE LOWER(table_name) = LOWER(%s) AND LOWER(table_schema) = LOWER(%s)",
                    (table_ref, schema_ref)
                )
            else:
                cur.execute(
                    "SELECT table_schema, table_name FROM information_schema.tables "
                    "WHERE LOWER(table_name) = LOWER(%s) "
                    "AND table_schema NOT IN ('pg_catalog', 'information_schema')",
                    (table_ref,)
                )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            tschema, tname = row[0], row[1]
            correct_quoted = f'{tschema}."{tname}"' if tschema != 'public' else f'"{tname}"'

            # 1) try replacing quoted identifier (exact quotes around ref)
            quoted_pattern = r'"' + re.escape(ref) + r'"'
            if re.search(quoted_pattern, sql_text):
                return re.sub(quoted_pattern, correct_quoted, sql_text)

            # 2) try replacing unquoted identifier (case-insensitive word boundary)
            unquoted_pattern = r'\b' + re.escape(ref) + r'\b'
            if re.search(unquoted_pattern, sql_text, re.IGNORECASE):
                return re.sub(unquoted_pattern, correct_quoted, sql_text, flags=re.IGNORECASE)

            return None
        except Exception:
            return None

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
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)
            for row in cursor.fetchall():
                tschema, tname, ttype_raw = row[0], row[1], row[2]
                display_name = tname if tschema == 'public' else f"{tschema}.{tname}"
                type_label = "VIEW" if ttype_raw == "VIEW" else "TABLE"
                columns: list[ColumnInfo] = []
                try:
                    cursor.execute("""
                        SELECT
                            c.column_name, c.data_type,
                            CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                            CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END,
                            c.column_default,
                            CASE WHEN c.is_identity = 'YES' THEN 1 ELSE 0 END,
                            c.character_maximum_length,
                            c.numeric_precision,
                            c.numeric_scale,
                            c.character_set_name,
                            c.collation_name,
                            cc.check_clause,
                            pgd.description
                        FROM information_schema.columns c
                        LEFT JOIN (
                            SELECT ku.column_name
                            FROM information_schema.table_constraints tc
                            JOIN information_schema.key_column_usage ku
                                ON tc.constraint_name = ku.constraint_name
                            WHERE tc.constraint_type = 'PRIMARY KEY'
                              AND tc.table_name = %s
                              AND tc.table_schema = %s
                        ) pk ON pk.column_name = c.column_name
                        LEFT JOIN information_schema.check_constraints cc
                            ON cc.constraint_name IN (
                                SELECT ccu.constraint_name
                                FROM information_schema.constraint_column_usage ccu
                                WHERE ccu.table_name = c.table_name
                                  AND ccu.column_name = c.column_name
                                  AND ccu.table_schema = c.table_schema
                                  AND ccu.constraint_name IN (
                                      SELECT constraint_name FROM information_schema.table_constraints
                                      WHERE constraint_type = 'CHECK'
                                        AND table_name = c.table_name
                                        AND table_schema = c.table_schema
                                  )
                            )
                        LEFT JOIN pg_catalog.pg_description pgd
                            ON pgd.objoid = (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass::oid
                            AND pgd.objsubid = c.ordinal_position
                        WHERE c.table_name = %s
                          AND c.table_schema = %s
                        ORDER BY c.ordinal_position
                    """, (tname, tschema, tname, tschema))
                    for c in cursor.fetchall():
                        columns.append(ColumnInfo(
                            name=c[0], data_type=c[1],
                            nullable=bool(c[2]), is_pk=bool(c[3]),
                            default_value=c[4],
                            is_identity=bool(c[5]),
                            char_length=c[6],
                            precision=c[7],
                            scale=c[8],
                            character_set=c[9] if c[9] else None,
                            collation=c[10] if c[10] else None,
                            check_constraint=c[11] if c[11] else None,
                            comment=c[12] if c[12] else None,
                        ))
                except Exception:
                    self._connection.rollback()
                    cursor.close()
                    return tables
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
                                AND ku.table_schema = tc.table_schema
                            JOIN information_schema.referential_constraints rc
                                ON tc.constraint_name = rc.constraint_name
                            JOIN information_schema.key_column_usage ref_ku
                                ON rc.unique_constraint_name = ref_ku.constraint_name
                            WHERE tc.constraint_type = 'FOREIGN KEY'
                              AND tc.table_name = %s
                              AND tc.table_schema = %s
                        """, (tname, tschema))
                        for fk in cursor.fetchall():
                            foreign_keys.append(ForeignKeyInfo(column=fk[0], ref_table=fk[1], ref_column=fk[2], fk_name=fk[3]))
                    except Exception:
                        self._connection.rollback()
                    try:
                        cursor.execute("""
                            SELECT indexname, indexdef
                            FROM pg_indexes
                            WHERE tablename = %s
                              AND schemaname = %s
                              AND indexname NOT LIKE '%_pkey'
                            ORDER BY indexname
                        """, (tname, tschema))
                        for ix in cursor.fetchall():
                            idx_name = ix[0]
                            idx_def = ix[1]
                            is_unique = "UNIQUE" in idx_def
                            cols_part = idx_def.split("(")[-1].rstrip(")") if "(" in idx_def else ""
                            idx_cols = [c.strip().strip('"') for c in cols_part.split(",")] if cols_part else []
                            indexes.append(IndexInfo(name=idx_name, columns=idx_cols, is_unique=is_unique))
                    except Exception:
                        self._connection.rollback()
                tables.append(TableInfo(name=display_name, type=type_label, columns=columns, foreign_keys=foreign_keys, indexes=indexes))
        except Exception:
            self._connection.rollback()
            return []
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
                        c.column_name, c.data_type,
                        CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                        CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END,
                        c.column_default,
                        CASE WHEN c.is_identity = 'YES' THEN 1 ELSE 0 END,
                        c.character_maximum_length,
                        c.numeric_precision,
                        c.numeric_scale,
                        c.character_set_name,
                        c.collation_name,
                        cc.check_clause,
                        pgd.description
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    LEFT JOIN information_schema.check_constraints cc
                        ON cc.constraint_name IN (
                            SELECT ccu.constraint_name
                            FROM information_schema.constraint_column_usage ccu
                            WHERE ccu.table_name = c.table_name
                              AND ccu.column_name = c.column_name
                              AND ccu.constraint_name IN (
                                  SELECT constraint_name FROM information_schema.table_constraints
                                  WHERE constraint_type = 'CHECK' AND table_name = c.table_name
                              )
                        )
                    LEFT JOIN pg_catalog.pg_description pgd
                        ON pgd.objoid = (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass::oid
                        AND pgd.objsubid = c.ordinal_position
                    WHERE c.table_name = %s
                      AND c.table_schema = %s
                    ORDER BY c.ordinal_position
                """, (table_name, table_name, schema))
            else:
                cursor.execute("""
                    SELECT
                        c.column_name, c.data_type,
                        CASE WHEN c.is_nullable = 'YES' THEN 1 ELSE 0 END,
                        CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END,
                        c.column_default,
                        CASE WHEN c.is_identity = 'YES' THEN 1 ELSE 0 END,
                        c.character_maximum_length,
                        c.numeric_precision,
                        c.numeric_scale,
                        c.character_set_name,
                        c.collation_name,
                        cc.check_clause,
                        pgd.description
                    FROM information_schema.columns c
                    LEFT JOIN (
                        SELECT ku.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage ku
                            ON tc.constraint_name = ku.constraint_name
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                    ) pk ON pk.column_name = c.column_name
                    LEFT JOIN information_schema.check_constraints cc
                        ON cc.constraint_name IN (
                            SELECT ccu.constraint_name
                            FROM information_schema.constraint_column_usage ccu
                            WHERE ccu.table_name = c.table_name
                              AND ccu.column_name = c.column_name
                              AND ccu.constraint_name IN (
                                  SELECT constraint_name FROM information_schema.table_constraints
                                  WHERE constraint_type = 'CHECK' AND table_name = c.table_name
                              )
                        )
                    LEFT JOIN pg_catalog.pg_description pgd
                        ON pgd.objoid = (quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass::oid
                        AND pgd.objsubid = c.ordinal_position
                    WHERE c.table_name = %s
                      AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY c.ordinal_position
                """, (table_name, table_name))
            for row in cursor.fetchall():
                result.append(ColumnInfo(
                    name=row[0], data_type=row[1],
                    nullable=bool(row[2]), is_pk=bool(row[3]),
                    default_value=row[4],
                    is_identity=bool(row[5]),
                    char_length=row[6],
                    precision=row[7],
                    scale=row[8],
                    character_set=row[9] if row[9] else None,
                    collation=row[10] if row[10] else None,
                    check_constraint=row[11] if row[11] else None,
                    comment=row[12] if row[12] else None,
                ))
        except Exception:
            self._connection.rollback()
            return []
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
                SELECT sequence_name, start_value, increment_by
                FROM information_schema.sequences
                WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY sequence_name
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
                    tg.tgname,
                    cl.relname,
                    pg_get_triggerdef(tg.oid)
                FROM pg_trigger tg
                JOIN pg_class cl ON tg.tgrelid = cl.oid
                WHERE tg.tgisinternal = false
                ORDER BY tg.tgname
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
                SELECT proname, prosrc
                FROM pg_proc
                WHERE pronamespace = 'public'::regnamespace
                  AND prokind = 'p'
                ORDER BY proname
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

    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]:
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
            return True, ""
        except psycopg2.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
