from dataclasses import dataclass, field
from datetime import datetime
from domain.enums import CommandType, ConnectionStatus
from domain.value_objects import SQLText


@dataclass
class SQLCommand:
    text: SQLText
    type: CommandType = CommandType.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.now)
    rows_affected: int = 0
    duration_ms: int = 0
    success: bool = False
    error_message: str = ""

    def __post_init__(self):
        self._detect_type()

    def _detect_type(self):
        stripped = self.text.value.strip().upper()
        for cmd_type in CommandType:
            if stripped.startswith(cmd_type.value):
                self.type = cmd_type
                return
        self.type = CommandType.UNKNOWN


@dataclass
class ExecutionResult:
    success: bool
    rows_affected: int
    duration_ms: int
    message: str
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)


@dataclass
class ConnectionSession:
    server: str
    database: str
    username: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    connected_at: datetime | None = None
    error_message: str = ""
