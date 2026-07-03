from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult, ProcedureInfo, SequenceInfo, TriggerInfo


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False
    default_value: str | None = None
    is_identity: bool = False
    identity_start: int | None = None
    identity_increment: int | None = None
    char_length: int | None = None
    precision: int | None = None
    scale: int | None = None
    character_set: str | None = None
    collation: str | None = None
    check_constraint: str | None = None
    comment: str | None = None


@dataclass
class ForeignKeyInfo:
    column: str
    ref_table: str
    ref_column: str
    fk_name: str = ""


@dataclass
class IndexInfo:
    name: str
    columns: list[str]
    is_unique: bool = False


@dataclass
class TableInfo:
    name: str
    type: str = "TABLE"  # TABLE | VIEW | PROCEDURE
    columns: list[ColumnInfo] = field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)


class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self, config: ConnectionConfig) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def execute(self, sql: SQLText) -> ExecutionResult: ...

    @abstractmethod
    def test_connection(self, config: ConnectionConfig) -> tuple[bool, str]: ...

    def get_schema(self) -> list[TableInfo]:
        return []

    def get_table_columns(self, table_name: str, schema: str | None = None) -> list[ColumnInfo]:
        return []

    def get_sequences(self) -> list[SequenceInfo]:
        return []

    def get_triggers(self) -> list[TriggerInfo]:
        return []

    def get_procedures(self) -> list[ProcedureInfo]:
        return []

    def get_connection(self):
        return self._connection if hasattr(self, "_connection") else None

    def executemany(self, sql_template: str, params: list[list]) -> ExecutionResult:
        """Execute the same SQL template with multiple parameter sets."""
        raise NotImplementedError

    def execute_autocommit(self, sql: SQLText) -> ExecutionResult:
        """Execute a statement outside transaction (default: same as execute)."""
        return self.execute(sql)


class CommandValidator(ABC):
    @abstractmethod
    def validate(self, sql: SQLText) -> None: ...


class AuditLogger(ABC):
    @abstractmethod
    def log_execution(self, sql: str, server: str, database: str, success: bool, rows: int, duration_ms: int) -> None: ...

    @abstractmethod
    def log_error(self, sql: str, server: str, database: str, error: str) -> None: ...

    @abstractmethod
    def log_connection(self, server: str, database: str, success: bool) -> None: ...
