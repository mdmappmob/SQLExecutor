from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    nullable: bool = True
    is_pk: bool = False


@dataclass
class TableInfo:
    name: str
    type: str = "TABLE"  # TABLE | VIEW | PROCEDURE
    columns: list[ColumnInfo] = field(default_factory=list)


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
    def test_connection(self, config: ConnectionConfig) -> bool: ...

    def get_schema(self) -> list[TableInfo]:
        return []

    def get_table_columns(self, table_name: str, schema: str | None = None) -> list[ColumnInfo]:
        return []

    def get_connection(self):
        return self._connection if hasattr(self, "_connection") else None


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
