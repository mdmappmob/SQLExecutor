from abc import ABC, abstractmethod
from domain.value_objects import ConnectionConfig, SQLText
from domain.entities import ExecutionResult


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
