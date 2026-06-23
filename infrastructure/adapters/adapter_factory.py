from domain.interfaces import DatabaseAdapter
from infrastructure.adapters.db_types import DBType


class AdapterFactory:
    _registry: dict[DBType, type[DatabaseAdapter]] = {}

    @classmethod
    def _lazy_load(cls, db_type: DBType) -> type[DatabaseAdapter]:
        if db_type == DBType.MSSQL:
            from infrastructure.adapters.mssql_adapter import MSSQLAdapter
            return MSSQLAdapter
        elif db_type == DBType.ORACLE:
            from infrastructure.adapters.oracle_adapter import OracleAdapter
            return OracleAdapter
        elif db_type == DBType.FIREBIRD:
            from infrastructure.adapters.firebird_adapter import FirebirdAdapter
            return FirebirdAdapter
        raise ValueError(f"Unsupported database type: {db_type.value}")

    @classmethod
    def create(cls, db_type: DBType | str) -> DatabaseAdapter:
        if isinstance(db_type, str):
            db_type = DBType(db_type)
        adapter_cls = cls._registry.get(db_type)
        if adapter_cls is None:
            adapter_cls = cls._lazy_load(db_type)
            cls._registry[db_type] = adapter_cls
        return adapter_cls()
