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

    _COLUMN_SELECT_WITH_IDENTITY = """
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
        CASE WHEN pk.RDB$FIELD_NAME IS NOT NULL THEN 1 ELSE 0 END,
        RF.RDB$DEFAULT_SOURCE,
        COALESCE(F.RDB$IDENTITY_TYPE, 0),
        CASE WHEN F.RDB$FIELD_TYPE IN (37, 14) THEN F.RDB$CHARACTER_LENGTH ELSE NULL END,
        F.RDB$FIELD_PRECISION,
        F.RDB$FIELD_SCALE,
        CS.RDB$CHARACTER_SET_NAME,
        NULL,
        F.RDB$VALIDATION_SOURCE,
        RF.RDB$DESCRIPTION
    """

    _COLUMN_SELECT_WITHOUT_IDENTITY = """
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
        CASE WHEN pk.RDB$FIELD_NAME IS NOT NULL THEN 1 ELSE 0 END,
        RF.RDB$DEFAULT_SOURCE,
        0,
        CASE WHEN F.RDB$FIELD_TYPE IN (37, 14) THEN F.RDB$CHARACTER_LENGTH ELSE NULL END,
        F.RDB$FIELD_PRECISION,
        F.RDB$FIELD_SCALE,
        CS.RDB$CHARACTER_SET_NAME,
        NULL,
        F.RDB$VALIDATION_SOURCE,
        RF.RDB$DESCRIPTION
    """

    def _execute_columns_query(self, table_name: str) -> list:
        cursor = self._connection.cursor()
        try:
            cursor.execute(f"""
                SELECT {self._COLUMN_SELECT_WITH_IDENTITY}
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
                LEFT JOIN RDB$CHARACTER_SETS CS ON F.RDB$CHARACTER_SET_ID = CS.RDB$CHARACTER_SET_ID
                WHERE RF.RDB$RELATION_NAME = ?
                ORDER BY RF.RDB$FIELD_POSITION
            """, (table_name, table_name))
            return cursor.fetchall()
        except fdb.Error as e:
            if "-206" in str(e):
                cursor.execute(f"""
                    SELECT {self._COLUMN_SELECT_WITHOUT_IDENTITY}
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
                    LEFT JOIN RDB$CHARACTER_SETS CS ON F.RDB$CHARACTER_SET_ID = CS.RDB$CHARACTER_SET_ID
                    WHERE RF.RDB$RELATION_NAME = ?
                    ORDER BY RF.RDB$FIELD_POSITION
                """, (table_name, table_name))
                return cursor.fetchall()
            raise
        finally:
            cursor.close()

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

    def execute_autocommit(self, sql: SQLText) -> ExecutionResult:
        return self.execute(sql)

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
        from domain.interfaces import TableInfo, ColumnInfo, ForeignKeyInfo, IndexInfo
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
                    seen_names: set[str] = set()
                    col_rows = self._execute_columns_query(tname)
                    for c in col_rows:
                        cname = c[0]
                        if cname in seen_names:
                            continue
                        seen_names.add(cname)
                        raw_scale = c[8]
                        scale = -raw_scale if raw_scale is not None and raw_scale < 0 else raw_scale
                        dv = c[4]
                        if dv and dv.strip().upper().startswith('DEFAULT '):
                            dv = dv.strip()[8:].strip()
                        columns.append(ColumnInfo(
                            name=cname, data_type=c[1],
                            nullable=not bool(c[2]), is_pk=bool(c[3]),
                            default_value=dv,
                            is_identity=bool(c[5]),
                            char_length=c[6],
                            precision=c[7],
                            scale=scale,
                            character_set=c[9] if c[9] else None,
                            check_constraint=c[11],
                            comment=c[12] if c[12] else None,
                        ))
                    foreign_keys: list[ForeignKeyInfo] = []
                    indexes: list[IndexInfo] = []
                    if type_label == "TABLE":
                        try:
                            cursor.execute("""
                                SELECT
                                    TRIM(seg.RDB$FIELD_NAME),
                                    TRIM(ref_rel.RDB$RELATION_NAME),
                                    TRIM(ref_seg.RDB$FIELD_NAME),
                                    TRIM(rc.RDB$CONSTRAINT_NAME)
                                FROM RDB$RELATION_CONSTRAINTS rc
                                JOIN RDB$REF_CONSTRAINTS refc ON rc.RDB$CONSTRAINT_NAME = refc.RDB$CONSTRAINT_NAME
                                JOIN RDB$INDEX_SEGMENTS seg ON rc.RDB$INDEX_NAME = seg.RDB$INDEX_NAME
                                JOIN RDB$RELATION_CONSTRAINTS ref_rc ON refc.RDB$PRIMARY_KEY = ref_rc.RDB$CONSTRAINT_NAME
                                JOIN RDB$INDEX_SEGMENTS ref_seg ON ref_rc.RDB$INDEX_NAME = ref_seg.RDB$INDEX_NAME
                                WHERE rc.RDB$CONSTRAINT_TYPE = 'FOREIGN KEY'
                                  AND rc.RDB$RELATION_NAME = ?
                                  AND seg.RDB$FIELD_POSITION = ref_seg.RDB$FIELD_POSITION
                            """, (tname,))
                            for fk in cursor.fetchall():
                                foreign_keys.append(ForeignKeyInfo(column=fk[0], ref_table=fk[1], ref_column=fk[2], fk_name=fk[3]))
                        except Exception:
                            pass
                        try:
                            cursor.execute("""
                                SELECT
                                    TRIM(i.RDB$INDEX_NAME),
                                    TRIM(s.RDB$FIELD_NAME),
                                    i.RDB$UNIQUE_FLAG,
                                    s.RDB$FIELD_POSITION
                                FROM RDB$INDICES i
                                JOIN RDB$INDEX_SEGMENTS s ON i.RDB$INDEX_NAME = s.RDB$INDEX_NAME
                                LEFT JOIN RDB$RELATION_CONSTRAINTS rc
                                    ON i.RDB$INDEX_NAME = rc.RDB$INDEX_NAME
                                    AND rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
                                WHERE i.RDB$RELATION_NAME = ?
                                  AND rc.RDB$CONSTRAINT_NAME IS NULL
                                ORDER BY i.RDB$INDEX_NAME, s.RDB$FIELD_POSITION
                            """, (tname,))
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
        seen_names: set[str] = set()
        for row in self._execute_columns_query(table_name):
            cname = row[0]
            if cname in seen_names:
                continue
            seen_names.add(cname)
            raw_scale = row[8]
            scale = -raw_scale if raw_scale is not None and raw_scale < 0 else raw_scale
            dv = row[4]
            if dv and dv.strip().upper().startswith('DEFAULT '):
                dv = dv.strip()[8:].strip()
            result.append(ColumnInfo(
                name=cname, data_type=row[1],
                nullable=not bool(row[2]), is_pk=bool(row[3]),
                default_value=dv,
                is_identity=bool(row[5]),
                char_length=row[6],
                precision=row[7],
                scale=scale,
                character_set=row[9] if row[9] else None,
                check_constraint=row[11],
                comment=row[12] if row[12] else None,
            ))
        return result

    def get_sequences(self) -> list[SequenceInfo]:
        from domain.entities import SequenceInfo
        result: list[SequenceInfo] = []
        if not self._connection:
            return result
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT
                    TRIM(G.RDB$GENERATOR_NAME),
                    G.RDB$INITIAL_VALUE,
                    G.RDB$GENERATOR_INCREMENT
                FROM RDB$GENERATORS G
                WHERE G.RDB$SYSTEM_FLAG = 0
                ORDER BY G.RDB$GENERATOR_NAME
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
                    TRIM(RDB$TRIGGER_NAME),
                    TRIM(RDB$RELATION_NAME),
                    RDB$TRIGGER_TYPE,
                    RDB$TRIGGER_SOURCE
                FROM RDB$TRIGGERS
                WHERE RDB$SYSTEM_FLAG = 0
                ORDER BY RDB$TRIGGER_NAME
            """)
            trigger_events = {
                1: "BEFORE INSERT", 2: "AFTER INSERT",
                3: "BEFORE UPDATE", 4: "AFTER UPDATE",
                5: "BEFORE DELETE", 6: "AFTER DELETE",
            }
            for row in cursor.fetchall():
                ttype = row[2]
                event = trigger_events.get(ttype, f"UNKNOWN({ttype})")
                body = row[3] or ""
                result.append(TriggerInfo(
                    name=row[0],
                    event=event,
                    body=body,
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
                SELECT
                    TRIM(RDB$PROCEDURE_NAME),
                    TRIM(RDB$PROCEDURE_SOURCE)
                FROM RDB$PROCEDURES
                WHERE RDB$SYSTEM_FLAG = 0
                ORDER BY RDB$PROCEDURE_NAME
            """)
            for row in cursor.fetchall():
                source = row[1] or ""
                result.append(ProcedureInfo(
                    name=row[0],
                    body=source,
                    source=source,
                ))
        finally:
            cursor.close()
        return result

    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]:
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
            return True, ""
        except fdb.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
