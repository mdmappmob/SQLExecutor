import os
import sys
import time

import oracledb

import logging

from domain.interfaces import DatabaseAdapter
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult
from infrastructure.i18n import I18N


logger = logging.getLogger(__name__)


def _get_client_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "infrastructure", "oracle_client")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "oracle_client")


_client_dir = _get_client_dir()
if os.path.isdir(_client_dir):
    oracledb.init_oracle_client(lib_dir=_client_dir)


class OracleAdapter(DatabaseAdapter):
    _connection: oracledb.Connection | None = None
    _server: str = ""
    _database: str = ""
    _has_collation: bool = True
    _has_identity_column: bool = True

    def _detect_columns(self) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute("""
                SELECT COLUMN_NAME
                FROM ALL_TAB_COLUMNS
                WHERE TABLE_NAME = 'ALL_TAB_COLUMNS'
                  AND OWNER = 'SYS'
                  AND COLUMN_NAME IN ('COLLATION', 'IDENTITY_COLUMN')
            """)
            existing = {row[0] for row in cursor.fetchall()}
            self._has_collation = 'COLLATION' in existing
            self._has_identity_column = 'IDENTITY_COLUMN' in existing
        except Exception:
            self._has_collation = False
            self._has_identity_column = False
        finally:
            cursor.close()

    def connect(self, config: ConnectionConfig) -> None:
        if self._connection:
            self.disconnect()
        self._server = config.server.value
        self._database = config.database.value
        dsn = config.database.value

        if config.use_windows_auth:
            self._connection = oracledb.connect(dsn=dsn)
        else:
            self._connection = oracledb.connect(
                user=config.username,
                password=config.password,
                dsn=dsn,
            )

        self._detect_columns()

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
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.close()
            return True
        except oracledb.Error:
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
        except oracledb.Error as e:
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
        result = self.execute(sql)
        if self._connection and result.success:
            self._connection.commit()
        return result

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
            except oracledb.Error as e:
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
            cursor.arraysize = 1000
            cursor.prefetchrows = 1000

            cursor.execute("""
                SELECT OBJECT_NAME, OBJECT_TYPE
                FROM ALL_OBJECTS
                WHERE OWNER = USER
                  AND OBJECT_TYPE IN ('TABLE', 'VIEW')
                ORDER BY OBJECT_NAME
            """)
            all_objects = cursor.fetchall()

            collation_col = "c.COLLATION" if self._has_collation else "NULL AS COLLATION"
            identity_expr = (
                "CASE WHEN c.IDENTITY_COLUMN = 'YES' THEN 1 ELSE 0 END"
                if self._has_identity_column else "0"
            )

            cursor.execute(f"""
                SELECT
                    c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE,
                    CASE WHEN c.NULLABLE = 'Y' THEN 1 ELSE 0 END,
                    CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END,
                    c.DATA_DEFAULT,
                    {identity_expr},
                    c.CHAR_LENGTH, c.DATA_PRECISION, c.DATA_SCALE,
                    c.CHARACTER_SET_NAME, {collation_col},
                    cc.SEARCH_CONDITION,
                    cm.COMMENTS
                FROM ALL_TAB_COLUMNS c
                LEFT JOIN (
                    SELECT pkcc.OWNER, pkcc.TABLE_NAME, pkcc.COLUMN_NAME
                    FROM ALL_CONSTRAINTS pk
                    JOIN ALL_CONS_COLUMNS pkcc
                        ON pk.CONSTRAINT_NAME = pkcc.CONSTRAINT_NAME
                       AND pk.OWNER = pkcc.OWNER
                    WHERE pk.CONSTRAINT_TYPE = 'P'
                      AND pk.OWNER = USER
                ) pk
                    ON pk.OWNER = c.OWNER
                   AND pk.TABLE_NAME = c.TABLE_NAME
                   AND pk.COLUMN_NAME = c.COLUMN_NAME
                LEFT JOIN (
                    SELECT ccu.TABLE_NAME, ccu.COLUMN_NAME, cc.SEARCH_CONDITION
                    FROM ALL_CONSTRAINTS cc
                    JOIN ALL_CONS_COLUMNS ccu
                        ON cc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
                       AND cc.OWNER = ccu.OWNER
                    WHERE cc.CONSTRAINT_TYPE = 'C'
                      AND cc.OWNER = USER
                ) cc
                    ON cc.TABLE_NAME = c.TABLE_NAME
                   AND cc.COLUMN_NAME = c.COLUMN_NAME
                LEFT JOIN ALL_COL_COMMENTS cm
                    ON cm.TABLE_NAME = c.TABLE_NAME
                    AND cm.COLUMN_NAME = c.COLUMN_NAME
                    AND cm.OWNER = c.OWNER
                WHERE c.OWNER = USER
                ORDER BY c.TABLE_NAME, c.COLUMN_ID
            """)

            col_map: dict[str, list[ColumnInfo]] = {}
            seen_cols: dict[str, set[str]] = {}
            for row in cursor.fetchall():
                tname = row[0]
                cname = row[1]
                if tname not in col_map:
                    col_map[tname] = []
                    seen_cols[tname] = set()
                if cname in seen_cols[tname]:
                    continue
                seen_cols[tname].add(cname)
                col_map[tname].append(ColumnInfo(
                    name=cname, data_type=row[2],
                    nullable=bool(row[3]), is_pk=bool(row[4]),
                    default_value=row[5],
                    is_identity=bool(row[6]),
                    char_length=row[7],
                    precision=row[8],
                    scale=row[9],
                    character_set=row[10] if row[10] else None,
                    collation=row[11] if row[11] else None,
                    check_constraint=row[12] if row[12] else None,
                    comment=row[13] if row[13] else None,
                ))

            obj_map = {obj[0]: obj[1] for obj in all_objects}
            table_names = [obj[0] for obj in all_objects if obj[1] == 'TABLE']

            fk_map: dict[str, list[ForeignKeyInfo]] = {}
            try:
                cursor.execute("""
                    SELECT
                        acc.TABLE_NAME, acc.COLUMN_NAME,
                        ref_acc.TABLE_NAME, ref_acc.COLUMN_NAME,
                        ac.CONSTRAINT_NAME
                    FROM ALL_CONSTRAINTS ac
                    JOIN ALL_CONS_COLUMNS acc
                        ON ac.CONSTRAINT_NAME = acc.CONSTRAINT_NAME
                       AND ac.OWNER = acc.OWNER
                    JOIN ALL_CONSTRAINTS ref_ac
                        ON ac.R_CONSTRAINT_NAME = ref_ac.CONSTRAINT_NAME
                       AND ac.R_OWNER = ref_ac.OWNER
                    JOIN ALL_CONS_COLUMNS ref_acc
                        ON ref_ac.CONSTRAINT_NAME = ref_acc.CONSTRAINT_NAME
                       AND ref_ac.OWNER = ref_acc.OWNER
                       AND acc.POSITION = ref_acc.POSITION
                    WHERE ac.CONSTRAINT_TYPE = 'R'
                      AND ac.OWNER = USER
                    ORDER BY acc.TABLE_NAME, ac.CONSTRAINT_NAME, acc.POSITION
                """)
                for row in cursor.fetchall():
                    tname = row[0]
                    if tname not in fk_map:
                        fk_map[tname] = []
                    fk_map[tname].append(ForeignKeyInfo(column=row[1], ref_table=row[2], ref_column=row[3], fk_name=row[4]))
            except Exception as e:
                logger.warning("Falha ao carregar foreign keys: %s", e)

            idx_map_outer: dict[str, list[IndexInfo]] = {}
            try:
                cursor.execute("""
                    SELECT ai.TABLE_NAME, ai.INDEX_NAME, aic.COLUMN_NAME, ai.UNIQUENESS, aic.COLUMN_POSITION
                    FROM ALL_INDEXES ai
                    JOIN ALL_IND_COLUMNS aic
                        ON ai.INDEX_NAME = aic.INDEX_NAME
                       AND ai.OWNER = aic.INDEX_OWNER
                    WHERE ai.OWNER = USER
                    ORDER BY ai.INDEX_NAME, aic.COLUMN_POSITION
                """)
                temp_idx: dict[str, dict[str, tuple[list[str], bool]]] = {}
                for row in cursor.fetchall():
                    tname = row[0]
                    iname = row[1]
                    if tname not in temp_idx:
                        temp_idx[tname] = {}
                    if iname not in temp_idx[tname]:
                        temp_idx[tname][iname] = ([], row[3] == 'UNIQUE')
                    temp_idx[tname][iname][0].append(row[2])
                for tname, idx_dict in temp_idx.items():
                    idx_map_outer[tname] = [
                        IndexInfo(name=iname, columns=icols, is_unique=iunique)
                        for iname, (icols, iunique) in idx_dict.items()
                    ]
            except Exception as e:
                logger.warning("Falha ao carregar índices: %s", e)

            for obj_name, obj_type in all_objects:
                tables.append(TableInfo(
                    name=obj_name, type=obj_type,
                    columns=col_map.get(obj_name, []),
                    foreign_keys=fk_map.get(obj_name, []),
                    indexes=idx_map_outer.get(obj_name, []),
                ))
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
            owner_clause = "AND c.OWNER = :1" if schema is None else "AND c.OWNER = :1"
            owner_val = schema or self._connection.username.upper() if hasattr(self._connection, 'username') else schema
            if owner_val is None:
                cursor.execute("SELECT USER FROM DUAL")
                owner_val = cursor.fetchone()[0]
            collation_col = "c.COLLATION" if self._has_collation else "NULL AS COLLATION"
            identity_expr = (
                "CASE WHEN c.IDENTITY_COLUMN = 'YES' THEN 1 ELSE 0 END"
                if self._has_identity_column else "0"
            )
            cursor.execute(f"""
                SELECT c.COLUMN_NAME, c.DATA_TYPE,
                       CASE WHEN c.NULLABLE = 'Y' THEN 1 ELSE 0 END,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM ALL_CONS_COLUMNS acc
                           JOIN ALL_CONSTRAINTS ac ON acc.CONSTRAINT_NAME = ac.CONSTRAINT_NAME
                           WHERE ac.CONSTRAINT_TYPE = 'P'
                             AND ac.OWNER = c.OWNER
                             AND acc.TABLE_NAME = c.TABLE_NAME
                             AND acc.COLUMN_NAME = c.COLUMN_NAME
                       ) THEN 1 ELSE 0 END,
                       c.DATA_DEFAULT,
                       {identity_expr},
                       c.CHAR_LENGTH, c.DATA_PRECISION, c.DATA_SCALE,
                       c.CHARACTER_SET_NAME, {collation_col},
                       cc.SEARCH_CONDITION,
                       cm.COMMENTS
                FROM ALL_TAB_COLUMNS c
                LEFT JOIN (
                    SELECT ccu.TABLE_NAME, ccu.COLUMN_NAME, cc.SEARCH_CONDITION
                    FROM ALL_CONSTRAINTS cc
                    JOIN ALL_CONS_COLUMNS ccu ON cc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
                    WHERE cc.CONSTRAINT_TYPE = 'C'
                      AND cc.OWNER = :1
                ) cc ON cc.TABLE_NAME = c.TABLE_NAME AND cc.COLUMN_NAME = c.COLUMN_NAME
                LEFT JOIN ALL_COL_COMMENTS cm
                    ON cm.TABLE_NAME = c.TABLE_NAME
                    AND cm.COLUMN_NAME = c.COLUMN_NAME
                    AND cm.OWNER = c.OWNER
                WHERE c.TABLE_NAME = :2
                  AND c.OWNER = :1
                ORDER BY c.COLUMN_ID
            """, [owner_val, table_name])
            seen: set[str] = set()
            for row in cursor.fetchall():
                cname = row[0]
                if cname in seen:
                    continue
                seen.add(cname)
                result.append(ColumnInfo(
                    name=cname, data_type=row[1],
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
                SELECT sequence_name, min_value, max_value, increment_by
                FROM all_sequences
                WHERE sequence_owner = USER
                ORDER BY sequence_name
            """)
            for row in cursor.fetchall():
                result.append(SequenceInfo(
                    name=row[0],
                    start_value=row[1] or 1,
                    increment=row[3] or 1,
                    min_value=row[1],
                    max_value=row[2],
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
                SELECT trigger_name, table_name, trigger_type, trigger_body
                FROM all_triggers
                WHERE owner = USER
                ORDER BY trigger_name
            """)
            for row in cursor.fetchall():
                result.append(TriggerInfo(
                    name=row[0],
                    event=row[2] or "",
                    body=row[3] or "",
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
            source_map: dict[str, list[str]] = {}
            cursor.execute("""
                SELECT name, text
                FROM (
                    SELECT object_name AS name, text
                    FROM all_source
                    WHERE owner = USER AND type = 'PROCEDURE'
                    ORDER BY object_name, line
                )
            """)
            for row in cursor.fetchall():
                name = row[0]
                if name not in source_map:
                    source_map[name] = []
                source_map[name].append(row[1] or "")
            for name, lines in source_map.items():
                source = ''.join(lines)
                result.append(ProcedureInfo(
                    name=name,
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
                conn = oracledb.connect(dsn=dsn)
            else:
                conn = oracledb.connect(
                    user=config.username,
                    password=config.password,
                    dsn=dsn,
                )
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.close()
            return True, ""
        except oracledb.Error as e:
            return False, str(e).strip()
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
