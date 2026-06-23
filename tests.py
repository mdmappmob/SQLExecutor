import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_value_objects():
    from domain.value_objects import ServerName, DatabaseName, SQLText, ConnectionConfig

    s = ServerName("localhost")
    assert s.value == "localhost"
    try:
        ServerName("")
        assert False
    except ValueError:
        pass

    d = DatabaseName("MyDB")
    assert d.value == "MyDB"

    sql = SQLText("SELECT 1")
    assert sql.is_dml
    assert not SQLText("DROP TABLE T").is_dml

    cfg = ConnectionConfig(db_type="mssql", server=ServerName("srv"), database=DatabaseName("db"), username="", password="", use_windows_auth=True)
    assert cfg.server.value == "srv"
    assert cfg.db_type == "mssql"

    print("  value_objects: OK")


def test_entities():
    from domain.value_objects import SQLText
    from domain.entities import SQLCommand, ExecutionResult
    from domain.enums import CommandType

    assert SQLCommand(text=SQLText("INSERT INTO T VALUES (1)")).type == CommandType.INSERT
    assert SQLCommand(text=SQLText("SELECT * FROM T")).type == CommandType.SELECT
    assert SQLCommand(text=SQLText("DELETE FROM T WHERE Id = 1")).type == CommandType.DELETE
    assert SQLCommand(text=SQLText("UPDATE T SET X=1")).type == CommandType.UPDATE
    assert SQLCommand(text=SQLText("CREATE TABLE T (Id int)")).type == CommandType.UNKNOWN

    res = ExecutionResult(True, 5, 100, "5 rows")
    assert res.rows_affected == 5
    assert res.success

    print("  entities + enums: OK")


def test_validator():
    from domain.value_objects import SQLText
    from application.use_cases import AllowedCommandsValidator

    v = AllowedCommandsValidator()

    for bad in ["DROP TABLE T", "TRUNCATE TABLE T", "ALTER TABLE T ADD X int", "CREATE TABLE T (Id int)"]:
        try:
            v.validate(SQLText(bad))
            assert False, f"{bad} should be blocked"
        except ValueError:
            pass

    try:
        v.validate(SQLText("DELETE FROM Users"))
        assert False
    except ValueError:
        pass

    v.validate(SQLText("DELETE FROM Users WHERE Id = 1"))
    v.validate(SQLText("INSERT INTO T VALUES (1)"))

    print("  validator: OK")


def test_config_manager():
    from infrastructure.config_manager import ConfigManager

    with tempfile.TemporaryDirectory() as tmp:
        cm = ConfigManager(os.path.join(tmp, "c.ini"))
        d = cm.load()
        assert d["server"] == ""
        assert d["timeout"] == 30

        cm.save({"db_type": "mssql", "server": "x", "database": "y", "username": "", "use_windows_auth": True, "timeout": 30})
        d2 = cm.load()
        assert d2["server"] == "x"
        assert d2["database"] == "y"
        assert d2["db_type"] == "mssql"
        assert os.path.isfile(os.path.join(tmp, "c.ini"))

    print("  config_manager: OK")


def test_logger():
    from infrastructure.logger import CSVLogger

    with tempfile.TemporaryDirectory() as tmp:
        log = CSVLogger(tmp)
        log.log_execution("SELECT 1", "srv", "db", True, 1, 5)
        log.log_error("BAD", "srv", "db", "syntax error")
        log.log_connection("srv", "db", True)

        assert os.path.isfile(os.path.join(tmp, "query_log.csv"))
        assert os.path.isfile(os.path.join(tmp, "error_log.csv"))
        assert os.path.isfile(os.path.join(tmp, "connection_log.csv"))

        with open(os.path.join(tmp, "query_log.csv")) as f:
            assert "SELECT 1" in f.read()

    print("  logger CSV: OK")


def test_use_cases():
    from domain.value_objects import SQLText
    from domain.entities import ExecutionResult
    from application.use_cases import ConnectionUseCase, SQLExecutionUseCase

    class MockAdapter:
        _server = _database = ""
        _connected = False

        def connect(self, config):
            self._server = config.server.value
            self._database = config.database.value
            self._connected = True

        def disconnect(self):
            self._connected = False

        def is_connected(self):
            return self._connected

        def execute(self, sql):
            if "FAIL" in sql.value:
                return ExecutionResult(False, 0, 10, "Simulated error")
            return ExecutionResult(True, 42, 50, "42 rows")

        def test_connection(self, config):
            return True

    class MockLogger:
        def __init__(self):
            self.logs = []

        def log_execution(self, sql, server, database, success, rows, duration_ms):
            self.logs.append(("exec", sql))

        def log_error(self, sql, server, database, error):
            self.logs.append(("err", sql))

        def log_connection(self, server, database, success):
            self.logs.append(("conn", server, database, success))

    adapter = MockAdapter()
    logger = MockLogger()
    conn_uc = ConnectionUseCase(adapter, logger)
    exec_uc = SQLExecutionUseCase(adapter, logger)

    session = conn_uc.connect("srv", "db", use_windows_auth=True)
    assert session.status.value == "Connected", session.status
    assert adapter._server == "srv"
    assert adapter._database == "db"
    print("  ConnectionUseCase.connect: OK")

    result = exec_uc.execute("INSERT INTO T VALUES (1)")
    assert result.success
    assert result.rows_affected == 42
    print("  SQLExecutionUseCase.execute (success): OK")

    adapter.execute = lambda sql: ExecutionResult(False, 0, 10, "Simulated adapter error")
    result2 = exec_uc.execute("SELECT * FROM T")
    assert not result2.success
    assert "Simulated adapter error" in result2.message
    print("  SQLExecutionUseCase.execute (adapter failure): OK")

    conn_uc.disconnect()
    assert not adapter.is_connected()
    print("  ConnectionUseCase.disconnect: OK")

    assert any(tag == "exec" for tag, *_ in logger.logs)
    assert any(tag == "conn" for tag, *_ in logger.logs)
    print("  Audit logging: OK")


def test_ui_imports():
    try:
        import PySide6  # noqa
    except ImportError:
        print("  SKIP: PySide6 not installed")
        return
    from ui.connection_dialog import ConnectionDialog
    from ui.sql_editor import SQLEditor
    from ui.result_panel import ResultPanel

    print("  UI module imports: OK")


if __name__ == "__main__":
    tests = [
        ("Value Objects", test_value_objects),
        ("Entities + Enums", test_entities),
        ("Validator", test_validator),
        ("ConfigManager", test_config_manager),
        ("Logger", test_logger),
        ("UseCases", test_use_cases),
        ("UI Imports", test_ui_imports),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  SQL Executor - Test Suite")
    print("=" * 60)
    print()

    for name, fn in tests:
        print(f"[{name}]")
        try:
            fn()
            passed += 1
            print(f"  -> PASS\n")
        except Exception as e:
            failed += 1
            import traceback
            print(f"  -> FAIL: {e}")
            traceback.print_exc()
            print()

    print("=" * 60)
    print(f"  Result: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)
