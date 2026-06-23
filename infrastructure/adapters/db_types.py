from enum import Enum


class DBType(Enum):
    MSSQL = "mssql"
    ORACLE = "oracle"
    FIREBIRD = "firebird"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.MSSQL.value, "SQL Server (MSSQL)"),
            (cls.ORACLE.value, "Oracle"),
            (cls.FIREBIRD.value, "Firebird"),
        ]

    @classmethod
    def default(cls) -> "DBType":
        return cls.MSSQL
