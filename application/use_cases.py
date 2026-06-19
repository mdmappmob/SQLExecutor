from datetime import datetime

from domain.enums import CommandType, ConnectionStatus
from domain.value_objects import ConnectionConfig, ServerName, DatabaseName, SQLText
from domain.entities import ConnectionSession, SQLCommand, ExecutionResult
from domain.interfaces import DatabaseAdapter, AuditLogger, CommandValidator
from infrastructure.i18n import I18N


class AllowedCommandsValidator(CommandValidator):
    ALLOWED = {CommandType.SELECT, CommandType.INSERT, CommandType.DELETE, CommandType.UPDATE}

    def validate(self, sql: SQLText) -> None:
        cmd = SQLCommand(text=sql)
        if cmd.type not in self.ALLOWED:
            raise ValueError(
                I18N.application["cmd_not_allowed"].format(
                    cmd=cmd.type.value,
                    allowed=", ".join(t.value for t in self.ALLOWED)
                )
            )
        if cmd.type == CommandType.DELETE:
            stripped = sql.value.strip().upper()
            if "WHERE" not in stripped:
                raise ValueError(I18N.application["delete_no_where"])


class ConnectionUseCase:
    def __init__(self, adapter: DatabaseAdapter, logger: AuditLogger):
        self._adapter = adapter
        self._logger = logger
        self.session = ConnectionSession(server="", database="", username="")

    def connect(
        self,
        server: str,
        database: str,
        username: str = "",
        password: str = "",
        use_windows_auth: bool = True,
        timeout: int = 30,
    ) -> ConnectionSession:
        self.session.status = ConnectionStatus.CONNECTING

        try:
            config = ConnectionConfig(
                server=ServerName(server),
                database=DatabaseName(database),
                username=username,
                password=password,
                use_windows_auth=use_windows_auth,
                timeout_seconds=timeout,
            )
            self._adapter.connect(config)
            self.session.server = server
            self.session.database = database
            self.session.username = username if not use_windows_auth else "Windows Auth"
            self.session.status = ConnectionStatus.CONNECTED
            self.session.connected_at = datetime.now()
            self.session.error_message = ""
            self._logger.log_connection(server, database, True)
        except Exception as e:
            self.session.status = ConnectionStatus.ERROR
            self.session.error_message = str(e)
            self._logger.log_connection(server, database, False)

        return self.session

    def disconnect(self) -> None:
        self._adapter.disconnect()
        self.session = ConnectionSession(server="", database="", username="")

    def test_connection(
        self,
        server: str,
        database: str,
        username: str = "",
        password: str = "",
        use_windows_auth: bool = True,
    ) -> bool:
        config = ConnectionConfig(
            server=ServerName(server),
            database=DatabaseName(database),
            username=username,
            password=password,
            use_windows_auth=use_windows_auth,
            timeout_seconds=10,
        )
        return self._adapter.test_connection(config)


class SQLExecutionUseCase:
    def __init__(self, adapter: DatabaseAdapter, logger: AuditLogger, validator: CommandValidator | None = None):
        self._adapter = adapter
        self._logger = logger
        self._validator = validator or AllowedCommandsValidator()

    def execute(self, sql_text: str) -> ExecutionResult:
        sql = SQLText(sql_text)

        self._validator.validate(sql)

        result = self._adapter.execute(sql)

        server = getattr(self._adapter, "_server", "unknown")
        database = getattr(self._adapter, "_database", "unknown")

        self._logger.log_execution(
            sql=sql.value,
            server=server,
            database=database,
            success=result.success,
            rows=result.rows_affected,
            duration_ms=result.duration_ms,
        )

        if not result.success:
            self._logger.log_error(
                sql=sql.value,
                server=server,
                database=database,
                error=result.message,
            )

        return result
