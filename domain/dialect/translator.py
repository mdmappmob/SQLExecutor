from sqlglot import transpile
import re


_SQLGLOT_DIALECTS: dict[str, str | None] = {
    "mssql": "tsql",
    "oracle": "oracle",
    "firebird": None,
    "mysql": "mysql",
    "mariadb": "mysql",
    "postgresql": "postgres",
    "sqlite": "sqlite",
}


def _clean(sql: str) -> str:
    return sql.strip().rstrip(";")


def _translate_via_sqlglot(sql: str, source: str, target: str) -> str | None:
    sg_source = _SQLGLOT_DIALECTS.get(source)
    sg_target = _SQLGLOT_DIALECTS.get(target)
    if not sg_source or not sg_target:
        return None
    try:
        result = transpile(sql, read=sg_source, write=sg_target)
        if result:
            return _clean(result[0])
    except Exception:
        pass
    return None


def _is_firebird(source: str, target: str) -> bool:
    return source == "firebird" or target == "firebird"


def _from_firebird(sql: str) -> str:
    m = re.match(
        r"SELECT\s+FIRST\s+(\d+)(?:\s+SKIP\s+(\d+))?\s+(.*)",
        sql,
        re.IGNORECASE,
    )
    if m:
        limit = m.group(1)
        offset = m.group(2)
        rest = m.group(3)
        if offset:
            return f"SELECT {rest} LIMIT {limit} OFFSET {offset}"
        else:
            return f"SELECT {rest} LIMIT {limit}"
    return sql


def _to_firebird(sql: str) -> str:
    m = re.search(
        r"LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?",
        sql,
        re.IGNORECASE,
    )
    if m:
        limit = m.group(1)
        offset = m.group(2)
        rest = re.sub(
            r"LIMIT\s+\d+(?:\s+OFFSET\s+\d+)?", "", sql, flags=re.IGNORECASE
        ).strip()
        if offset:
            return f"SELECT FIRST {limit} SKIP {offset} {rest[6:].strip()}"
        else:
            return f"SELECT FIRST {limit} {rest[6:].strip()}"
    return sql


def _map_identifiers(sql: str, target: str) -> str:
    if target == "firebird":
        sql = re.sub(r'\[(\w+)\]', r'"\1"', sql)
        sql = re.sub(r'`(\w+)`', r'"\1"', sql)
    elif target in ("mysql", "mariadb"):
        sql = re.sub(r'\[(\w+)\]', r'`\1`', sql)
        sql = re.sub(r'"(\w+)"', r'`\1`', sql)
    elif target in ("oracle", "postgresql"):
        sql = re.sub(r'\[(\w+)\]', r'"\1"', sql)
        sql = re.sub(r'`(\w+)`', r'"\1"', sql)
    elif target == "sqlite":
        sql = sql.replace("[", '"').replace("]", '"')
    else:
        sql = re.sub(r'`(\w+)`', r'[\1]', sql)
        sql = re.sub(r'"(\w+)"', r'[\1]', sql)
    return sql


def translate(sql: str, source: str, target: str) -> str:
    if source == target:
        return _clean(sql)

    sql = _clean(sql)
    work = sql

    if source == "firebird":
        work = _from_firebird(work)
        work = _translate_via_sqlglot(work, "postgresql", target) or work
        work = _to_firebird(work) if target == "firebird" else work
    elif target == "firebird":
        work = _translate_via_sqlglot(sql, source, "postgresql") or sql
        work = _to_firebird(work)
    else:
        result = _translate_via_sqlglot(sql, source, target)
        if result:
            work = result

    work = _map_identifiers(work, target)
    return work
