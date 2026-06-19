import configparser
import os


class ConfigManager:
    _file_path: str

    def __init__(self, file_path: str = "config.ini"):
        self._file_path = file_path

    def load(self) -> dict:
        config = configparser.ConfigParser()
        config.read(self._file_path)

        if "Connection" not in config:
            return self._defaults()

        return {
            "server": config.get("Connection", "server", fallback=""),
            "database": config.get("Connection", "database", fallback=""),
            "username": config.get("Connection", "username", fallback=""),
            "password": config.get("Connection", "password", fallback=""),
            "use_windows_auth": config.getboolean("Connection", "use_windows_auth", fallback=True),
            "timeout": config.getint("Connection", "timeout", fallback=30),
        }

    def save(self, data: dict) -> None:
        config = configparser.ConfigParser()
        config["Connection"] = {
            "server": data.get("server", ""),
            "database": data.get("database", ""),
            "username": data.get("username", ""),
            "password": data.get("password", ""),
            "use_windows_auth": str(data.get("use_windows_auth", True)),
            "timeout": str(data.get("timeout", 30)),
        }
        with open(self._file_path, "w", encoding="utf-8") as f:
            config.write(f)

    def has_config(self) -> bool:
        config = configparser.ConfigParser()
        config.read(self._file_path)
        if "Connection" not in config:
            return False
        server = config.get("Connection", "server", fallback="")
        database = config.get("Connection", "database", fallback="")
        return bool(server and database)

    def _defaults(self) -> dict:
        return {
            "server": "",
            "database": "",
            "username": "",
            "password": "",
            "use_windows_auth": True,
            "timeout": 30,
        }

    @property
    def file_path(self) -> str:
        return os.path.abspath(self._file_path)
