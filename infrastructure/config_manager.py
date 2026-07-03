import configparser
import os
import platform
import base64
from pathlib import Path


def _get_config_dir() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(base) / "SQLExecutor"


def _get_config_path() -> Path:
    return _get_config_dir() / "sqlexecutor.ini"


_KEYRING_SERVICE = "SQLExecutor"


def _store_password_keyring(username: str, password: str) -> bool:
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, username, password)
        return True
    except Exception:
        return False


def _load_password_keyring(username: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(_KEYRING_SERVICE, username)
    except Exception:
        return None


def _delete_password_keyring(username: str) -> None:
    try:
        import keyring
        try:
            keyring.delete_password(_KEYRING_SERVICE, username)
        except keyring.errors.PasswordDeleteError:
            pass
    except Exception:
        pass


def _obfuscate(plain: str) -> str:
    return base64.b64encode(plain.encode()).decode()


def _deobfuscate(encoded: str) -> str:
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return ""


class ConfigManager:
    _file_path: Path

    def __init__(self, file_path: str | None = None):
        self._file_path = Path(file_path) if file_path else _get_config_path()

    def load(self) -> dict:
        config = configparser.ConfigParser()
        config.read(self._file_path, encoding="utf-8")

        if "Connection" not in config:
            return self._defaults()

        section = config["Connection"]
        username = section.get("username", fallback="")
        password = ""

        if username and not section.getboolean("use_windows_auth", fallback=False):
            password = _load_password_keyring(username)
            if password is None:
                b64 = section.get("_password_b64", fallback="")
                password = _deobfuscate(b64) if b64 else ""

        return {
            "db_type": section.get("db_type", fallback="mssql"),
            "server": section.get("server", fallback=""),
            "database": section.get("database", fallback=""),
            "username": username,
            "password": password,
            "use_windows_auth": section.getboolean("use_windows_auth", fallback=True),
            "timeout": section.getint("timeout", fallback=30),
            "port": section.getint("port", fallback=None),
        }

    def save(self, data: dict) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)

        config = configparser.ConfigParser()
        connection_data = {
            "db_type": data.get("db_type", "mssql"),
            "server": data.get("server", ""),
            "database": data.get("database", ""),
            "username": data.get("username", ""),
            "use_windows_auth": str(data.get("use_windows_auth", True)),
            "timeout": str(data.get("timeout", 30)),
        }
        port = data.get("port")
        if port:
            connection_data["port"] = str(port)
        config["Connection"] = connection_data

        username = data.get("username", "")
        password = data.get("password", "")

        if username and password and not data.get("use_windows_auth", False):
            if not _store_password_keyring(username, password):
                config["Connection"]["_password_b64"] = _obfuscate(password)

        with open(self._file_path, "w", encoding="utf-8") as f:
            config.write(f)

    def has_config(self) -> bool:
        config = configparser.ConfigParser()
        config.read(self._file_path, encoding="utf-8")
        if "Connection" not in config:
            return False
        server = config.get("Connection", "server", fallback="")
        database = config.get("Connection", "database", fallback="")
        return bool(server and database)

    def clear_password(self) -> None:
        data = self.load()
        username = data.get("username", "")
        if username:
            _delete_password_keyring(username)
        if self._file_path.exists():
            self._file_path.unlink(missing_ok=True)

    def _defaults(self) -> dict:
        return {
            "db_type": "mssql",
            "server": "",
            "database": "",
            "username": "",
            "password": "",
            "use_windows_auth": True,
            "timeout": 30,
            "port": None,
        }

    @property
    def file_path(self) -> str:
        return str(self._file_path.resolve())
