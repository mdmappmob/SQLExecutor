from enum import Enum


class DBType(Enum):
    MSSQL = "mssql"
    ORACLE = "oracle"
    FIREBIRD = "firebird"
    MYSQL = "mysql"
    MARIADB = "mariadb"
    POSTGRESQL = "postgresql"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [
            (cls.MSSQL.value, "SQL Server (MSSQL)"),
            (cls.ORACLE.value, "Oracle"),
            (cls.FIREBIRD.value, "Firebird"),
            (cls.MYSQL.value, "MySQL"),
            (cls.MARIADB.value, "MariaDB"),
            (cls.POSTGRESQL.value, "PostgreSQL"),
        ]

    @classmethod
    def default(cls) -> "DBType":
        return cls.MSSQL
