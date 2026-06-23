from dataclasses import dataclass
import re

from infrastructure.i18n import I18N


@dataclass(frozen=True)
class ServerName:
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError(I18N.domain["server_empty"])
        if len(self.value) > 256:
            raise ValueError(I18N.domain["server_long"])


@dataclass(frozen=True)
class DatabaseName:
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("Database name cannot be empty")
        if len(self.value) > 128:
            raise ValueError("Database name too long (max 128 chars)")


@dataclass(frozen=True)
class SQLText:
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("SQL text cannot be empty")

    @property
    def is_dml(self) -> bool:
        stripped = self.value.strip().upper()
        return any(stripped.startswith(kw) for kw in ("INSERT", "DELETE", "UPDATE", "SELECT"))


@dataclass(frozen=True)
class ConnectionConfig:
    db_type: str
    server: ServerName
    database: DatabaseName
    username: str
    password: str
    use_windows_auth: bool
    timeout_seconds: int = 30
    encrypt: bool = False
    trust_server_certificate: bool = True
