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
        stripped = self.text.value.strip()
        upper = stripped.upper()

        for cmd_type in CommandType:
            if upper.startswith(cmd_type.value):
                self.type = cmd_type
                return

        if upper.startswith("WITH"):
            depth = 0
            n = len(upper)
            for i in range(n):
                if upper[i] == '(':
                    depth += 1
                elif upper[i] == ')':
                    depth -= 1
                elif depth == 0:
                    for cmd_type in CommandType:
                        if cmd_type == CommandType.UNKNOWN:
                            continue
                        if upper[i:].startswith(cmd_type.value):
                            end = i + len(cmd_type.value)
                            if end >= n or not (upper[end].isalnum() or upper[end] == '_'):
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
