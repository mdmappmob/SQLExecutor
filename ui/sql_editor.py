from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel,
    QLineEdit, QTextEdit, QTabWidget, QToolButton, QTabBar,
    QInputDialog, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QEvent, QPoint, QSize
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument, QColor, QShortcut, QKeySequence, QIcon, QPixmap, QPolygon, QBrush, QPen, QPainter

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.generator import Generator

from infrastructure.i18n import I18N
from ui.dialogs import show_critical


class _SQLHighlighter(QSyntaxHighlighter):
    _KEYWORDS = {
        "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "EXISTS",
        "BETWEEN", "LIKE", "IS", "NULL", "AS", "ON", "JOIN", "LEFT",
        "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "UNION", "ALL",
        "DISTINCT", "ORDER", "BY", "GROUP", "HAVING", "ASC", "DESC",
        "LIMIT", "OFFSET", "TOP", "INSERT", "INTO", "VALUES", "UPDATE",
        "SET", "DELETE", "CREATE", "TABLE", "ALTER", "DROP", "INDEX",
        "VIEW", "PROCEDURE", "FUNCTION", "TRIGGER", "IF", "THEN", "ELSE",
        "END", "CASE", "WHEN", "BEGIN", "COMMIT", "ROLLBACK", "DECLARE",
        "CURSOR", "FETCH", "OPEN", "CLOSE", "RETURN", "EXEC", "EXECUTE",
        "COUNT", "SUM", "AVG", "MIN", "MAX", "CAST", "CONVERT",
        "COALESCE", "NULLIF", "WITH", "RECURSIVE", "OVER", "PARTITION",
        "ROW_NUMBER", "RANK", "DENSE_RANK", "PRIMARY", "KEY", "FOREIGN",
        "REFERENCES", "CONSTRAINT", "DEFAULT", "CHECK", "UNIQUE",
        "AUTO_INCREMENT", "IDENTITY", "INT", "INTEGER", "VARCHAR", "CHAR",
        "TEXT", "BOOLEAN", "DATE", "TIMESTAMP", "FLOAT", "DOUBLE",
        "DECIMAL", "NUMERIC", "BLOB", "CLOB", "BIGINT", "SMALLINT",
        "TINYINT", "TRUE", "FALSE", "FIRST", "SKIP", "ROWS", "FETCH",
        "NEXT", "ONLY", "TRUNCATE", "MERGE", "MATCHED", "EXCEPT",
        "INTERSECT", "SOME", "ANY", "EACH", "USING", "NATURAL",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self._keyword_fmt = QTextCharFormat()
        self._keyword_fmt.setForeground(QColor("#DCDCAA"))
        self._keyword_fmt.setFontWeight(75)

        self._string_fmt = QTextCharFormat()
        self._string_fmt.setForeground(QColor("#F0C674"))

        self._number_fmt = QTextCharFormat()
        self._number_fmt.setForeground(QColor("#B5E853"))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setFontItalic(True)
        self._comment_fmt.setForeground(QColor("#5C6370"))

        self._operator_fmt = QTextCharFormat()
        self._operator_fmt.setForeground(QColor("#D19A66"))

    def highlightBlock(self, text):
        n = len(text)
        state = self.previousBlockState()
        i = 0

        if state == 1:
            end = text.find('*/')
            if end >= 0:
                self.setFormat(0, end + 2, self._comment_fmt)
                self.setCurrentBlockState(0)
                i = end + 2
            else:
                self.setFormat(0, n, self._comment_fmt)
                self.setCurrentBlockState(1)
                return

        while i < n:
            ch = text[i]

            if ch == "'":
                end = self._find_string_end(text, i + 1)
                self.setFormat(i, end - i + 1, self._string_fmt)
                i = end + 1
                continue

            if ch == '/' and i + 1 < n and text[i + 1] == '*':
                end = text.find('*/', i + 2)
                if end == -1:
                    self.setFormat(i, n - i, self._comment_fmt)
                    self.setCurrentBlockState(1)
                    return
                self.setFormat(i, end - i + 2, self._comment_fmt)
                i = end + 2
                continue

            if ch == '-' and i + 1 < n and text[i + 1] == '-':
                self.setFormat(i, n - i, self._comment_fmt)
                self.setCurrentBlockState(0)
                return

            if ch.isdigit():
                j = i
                while j < n and (text[j].isdigit() or text[j] == '.'):
                    j += 1
                self.setFormat(i, j - i, self._number_fmt)
                i = j
                continue

            if ch.isalpha() or ch == '_':
                j = i
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                word = text[i:j].upper()
                if word in self._KEYWORDS:
                    self.setFormat(i, j - i, self._keyword_fmt)
                i = j
                continue

            if ch in "=<>!+-*/%()[],.":
                self.setFormat(i, 1, self._operator_fmt)
                i += 1
                continue

            i += 1

        self.setCurrentBlockState(0)

    @staticmethod
    def _find_string_end(text: str, start: int) -> int:
        i = start
        n = len(text)
        while i < n:
            if text[i] == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                return i
            i += 1
        return n - 1


def split_sql_statements(sql: str) -> list[str]:
    statements = []
    current = []
    i = 0
    n = len(sql)
    while i < n:
        c = sql[i]
        if c == "'":
            current.append(c)
            i += 1
            while i < n:
                current.append(sql[i])
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 1
                        current.append(sql[i])
                    else:
                        break
                i += 1
            i += 1
            continue
        if c == '-' and i + 1 < n and sql[i + 1] == '-':
            end = sql.find('\n', i + 2)
            if end == -1:
                break
            i = end + 1
            continue
        if c == '/' and i + 1 < n and sql[i + 1] == '*':
            end = sql.find('*/', i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        if c == ';':
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    stmt = ''.join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def strip_sql_comments(sql: str) -> str:
    result = []
    i = 0
    n = len(sql)
    while i < n:
        if sql[i:i + 2] == '/*':
            end = sql.find('*/', i + 2)
            if end == -1:
                break
            i = end + 2
            continue
        if sql[i:i + 2] == '--':
            end = sql.find('\n', i + 2)
            if end == -1:
                break
            i = end + 1
            continue
        result.append(sql[i])
        i += 1
    return ''.join(result).strip()


_SELECT_WRAP = 88
_GROUP_WRAP = 130


class _NoAsGenerator(Generator):
    def table_sql(self, expression, sep=" "):
        return super().table_sql(expression, sep=sep)

    def subquery_sql(self, expression, sep=" "):
        return super().subquery_sql(expression, sep=sep)

    def values_sql(self, expression, values_as_table=True):
        values_as_table = values_as_table and self.VALUES_AS_TABLE
        if values_as_table or not expression.find_ancestor(exp.From, exp.Join):
            args = self.expressions(expression)
            alias = self.sql(expression, "alias")
            values = f"VALUES{self.seg('')}{args}"
            values = (
                f"({values})"
                if self.WRAP_DERIVED_VALUES
                and (alias or isinstance(expression.parent, (exp.From, exp.Table)))
                else values
            )
            values = self.query_modifiers(expression, values)
            return f"{values} {alias}" if alias else values
        return super().values_sql(expression, values_as_table=values_as_table)


def _is_select(e):
    return isinstance(e, exp.Select)


def _unwrap_paren(e):
    while isinstance(e, exp.Paren):
        e = e.this
    return e


def _conjuncts(e):
    out = []
    stack = [_unwrap_paren(e)]
    while stack:
        c = stack.pop()
        if isinstance(c, exp.And):
            stack.append(_unwrap_paren(c.this))
            if c.expression is not None:
                stack.append(_unwrap_paren(c.expression))
        else:
            out.append(c)
    out.reverse()
    return out


def _disjuncts(e):
    out = []
    stack = [_unwrap_paren(e)]
    while stack:
        c = stack.pop()
        if isinstance(c, exp.Or):
            stack.append(_unwrap_paren(c.this))
            if c.expression is not None:
                stack.append(_unwrap_paren(c.expression))
        else:
            out.append(c)
    out.reverse()
    return out


def _join_keyword(j):
    side = (j.args.get("side") or "").upper()
    kind = (j.args.get("kind") or "").upper()
    method = (j.args.get("method") or "").upper()
    if method == "NATURAL":
        return "NATURAL JOIN"
    if method == "CROSS":
        return "CROSS JOIN"
    if side == "FULL":
        return "FULL OUTER JOIN" if kind == "OUTER" else "FULL JOIN"
    if side == "LEFT":
        return "LEFT JOIN"
    if side == "RIGHT":
        return "RIGHT JOIN"
    return "JOIN"


def _alias_text(gen, sub):
    a = sub.args.get("alias")
    if a is None:
        return ""
    name = gen.sql(a.this) if a.this is not None else ""
    cols = a.args.get("columns")
    if cols:
        coltxt = ", ".join(gen.sql(c) for c in cols)
        return f"{name}({coltxt})"
    return name


def _pack(items, indent_col, width):
    lines = []
    cur = []
    cur_len = indent_col
    for i, it in enumerate(items):
        sep = 0 if not cur else 2
        if cur and cur_len + sep + len(it) + 1 > width:
            lines.append(", ".join(cur) + ",")
            cur = []
            cur_len = indent_col
            sep = 0
        cur.append(it)
        cur_len += sep + len(it)
    if cur:
        lines.append(", ".join(cur))
    return lines


def _pack_with_prefix(first_prefix, items, kw_col, width):
    indent_col = kw_col + len(first_prefix) + 1
    lines = _pack(items, indent_col, width)
    first = " " * kw_col + first_prefix + " " + lines[0]
    out = [first]
    for ln in lines[1:]:
        out.append(" " * indent_col + ln)
    return out


class _Unsupported(Exception):
    pass


class _CompactSQLGenerator(object):
    def __init__(self):
        self.g = _NoAsGenerator(pretty=False)

    def fmt_stmt(self, node):
        if isinstance(node, exp.Select):
            if not self._supported_select(node):
                return None
            with_ = node.args.get("with_")
            if with_ is not None:
                lines = self._with_lines(with_)
                if lines is None:
                    return None
                lines.extend(self.render_select(node, 0))
                return lines
            return self.render_select(node, 0)
        if isinstance(node, (exp.Union, exp.Except, exp.Intersect)):
            out = []
            with_ = node.args.get("with_")
            if with_ is not None:
                wl = self._with_lines(with_)
                if wl is None:
                    return None
                out.extend(wl)
            body = self._set_lines(node)
            if body is None:
                return None
            out.extend(body)
            return out
        return None

    def _supported_select(self, sel):
        allowed = {
            "kind", "hint", "distinct", "top", "expressions", "limit", "exclude",
            "operation_modifiers", "into", "from_", "joins", "where", "group",
            "having", "qualify", "connect", "order", "lateral", "with_", "offset",
            "prewhere", "match", "sample", "laterals", "for",
        }
        for k, v in sel.args.items():
            if v is None or (isinstance(v, list) and not v):
                continue
            if k not in allowed:
                return False
        for k in ("into", "qualify", "connect", "lateral", "laterals", "prewhere", "sample", "match", "hint"):
            if sel.args.get(k) is not None:
                return False
        if sel.args.get("operation_modifiers"):
            return False
        if sel.args.get("exclude") is not None:
            return False
        return True

    def _collect_sets(self, node, acc):
        if isinstance(node, exp.Select):
            acc.append((node, None))
            return
        if isinstance(node, (exp.Union, exp.Except, exp.Intersect)):
            self._collect_sets(node.this, acc)
            if isinstance(node, exp.Union):
                key = "UNION ALL" if node.args.get("distinct") is False else "UNION"
            elif isinstance(node, exp.Except):
                key = "EXCEPT ALL" if node.args.get("distinct") is False else "EXCEPT"
            else:
                key = "INTERSECT ALL" if node.args.get("distinct") is False else "INTERSECT"
            acc.append((node.expression, key))
            return
        raise _Unsupported

    def _set_lines(self, node):
        pieces = []
        self._collect_sets(node, pieces)
        out = []
        order = node.args.get("order")
        for idx, (sel, opkw) in enumerate(pieces):
            if opkw is not None:
                out.append("")
                out.append(opkw)
                out.append("")
            if not self._supported_select(sel):
                return None
            with_ = sel.args.get("with_")
            if with_ is not None:
                wl = self._with_lines(with_)
                if wl is None:
                    return None
                out.extend(wl)
            lines = self.render_select(sel, 0)
            out.extend(lines)
        if order is not None:
            orditems = [self.g.sql(o) for o in order.expressions] if getattr(order, "expressions", None) else None
            if orditems:
                out.append(" ORDER BY " + ", ".join(orditems))
            else:
                out.append(" " + self.g.sql(order))
        return out

    def _with_lines(self, with_):
        ctes = with_.expressions
        head = "WITH RECURSIVE " if with_.args.get("recursive") else "WITH "
        parts = []
        for cte in ctes:
            a = cte.args.get("alias")
            name = self.g.sql(a.this) if a is not None and a.this is not None else self.g.sql(cte.this)
            cols = a.args.get("columns") if a is not None else None
            coltxt = ""
            if cols:
                coltxt = "(" + ", ".join(self.g.sql(c) for c in cols) + ")"
            body = cte.this
            if isinstance(body, exp.Subquery):
                body = body.this
            if isinstance(body, exp.Paren):
                body = body.this
            if not _is_select(body) and not isinstance(body, (exp.Union, exp.Except, exp.Intersect)):
                parts.append(f"{name}{coltxt} AS ({self.g.sql(body)})")
            else:
                flat = self.g.sql(body)
                if len(flat) <= 90:
                    parts.append(f"{name}{coltxt} AS ({flat})")
                else:
                    parts.append(self._cte_block(name + coltxt, body))
        if any(not isinstance(p, str) for p in parts):
            return None
        total = head + ", ".join(parts)
        if len(total) <= _SELECT_WRAP + 40:
            return [total]
        lines = []
        cur = head
        for i, p in enumerate(parts):
            cur += ("" if i == 0 else ", ") + p
            if len(cur) > _SELECT_WRAP + 30 and i < len(parts) - 1:
                lines.append(cur)
                cur = " " * len(head)
        if cur.strip():
            lines.append(cur)
        return lines

    def _cte_block(self, name, body):
        lines = self.render_block_after(f"{name} AS (", body, 0)
        if lines is None:
            return None
        return "\n".join(lines)

    def render_block_after(self, prefix, body, prefix_col):
        if _is_select(body):
            lines = self.render_select(body, prefix_col + len(prefix))
            first = lines[0]
            head = " " * prefix_col + prefix + first[prefix_col + len(prefix):]
            out = [head]
            out.extend(lines[1:])
            out[-1] = out[-1] + ")"
            return out
        if isinstance(body, (exp.Union, exp.Except, exp.Intersect)):
            sub = self._set_lines_embedded(body, prefix_col + len(prefix))
            if sub is None:
                return None
            first = sub[0]
            out = [" " * prefix_col + prefix + first[prefix_col + len(prefix):]]
            out.extend(sub[1:])
            out[-1] = out[-1] + ")"
            return out
        return None

    def render_select(self, sel, s_col):
        lines = self._select_header(sel, s_col)
        frm = sel.args.get("from_")
        joins = sel.args.get("joins") or []
        where = sel.args.get("where")
        group = sel.args.get("group")
        having = sel.args.get("having")
        order = sel.args.get("order")
        limit = sel.args.get("limit")
        offset = sel.args.get("offset")
        if frm is not None:
            r = self._from_lines(frm, s_col)
            if r is None:
                raise _Unsupported()
            lines.extend(r)
        for j in joins:
            r = self._join_lines(j, s_col)
            if r is None:
                raise _Unsupported()
            lines.extend(r)
        if where is not None:
            lines.extend(self._cond_lines("WHERE", where.this, s_col, s_col + 1, s_col + 3, pad_eq=True))
        if group is not None:
            lines.extend(self._group_lines(group, s_col))
        if having is not None:
            lines.extend(self._having_lines(having.this, s_col))
        if order is not None:
            lines.extend(self._order_lines(order, s_col))
        if limit is not None:
            lines.append(" " * (s_col + 1) + self.g.sql(limit))
        if offset is not None:
            lines.append(" " * (s_col + 1) + self.g.sql(offset))
        return lines

    def _select_header(self, sel, s_col):
        prefix = "SELECT"
        d = sel.args.get("distinct")
        if d is not None:
            prefix += " " + self.g.sql(d)
        exprs = sel.args.get("expressions") or []
        if not exprs:
            return [" " * s_col + prefix]
        items = []
        for e in exprs:
            t = self._item_text(e)
            if t is None:
                raise _Unsupported()
            items.append(t)
        return _pack_with_prefix(prefix, items, s_col, _SELECT_WRAP)

    def _item_text(self, e):
        if isinstance(e, exp.Alias):
            inner = _unwrap_paren(e.this)
            aname = e.args.get("alias")
            if aname is not None and isinstance(inner, exp.Column):
                colname = self.g.sql(inner)
                aliasn = self.g.sql(aname)
                if colname == aliasn or colname.endswith("." + aliasn):
                    return colname
            if isinstance(e.this, exp.Paren) and not isinstance(inner, (exp.Subquery, exp.Select)):
                e2 = e.copy()
                e2.set("this", inner)
                return self.g.sql(e2)
            return self.g.sql(e)
        u = e
        if isinstance(u, exp.Paren):
            inner = u.this
            if isinstance(inner, (exp.Subquery, exp.Select)):
                return self.g.sql(u)
            return self.g.sql(inner)
        txt = self.g.sql(u)
        if txt == "":
            return None
        return txt

    def _from_lines(self, frm, s_col):
        src = frm.this
        indent = s_col + 2
        if isinstance(src, exp.Table):
            return [" " * indent + "FROM " + self.g.sql(src)]
        if isinstance(src, exp.Subquery):
            inner = src.this
            if _is_select(inner):
                sub_col = indent + len("FROM") + 2
                lines = self.render_select(inner, sub_col)
                first = lines[0]
                out = [" " * indent + "FROM (" + first[sub_col:]]
                out.extend(lines[1:])
                out[-1] = out[-1] + ")" + self._sp_plus_alias(src)
                return out
            if isinstance(inner, (exp.Union, exp.Except, exp.Intersect)):
                raise _Unsupported()
            return [" " * indent + "FROM " + self.g.sql(src)]
        if isinstance(src, exp.Values):
            return [" " * indent + "FROM " + self.g.sql(src)]
        raise _Unsupported()

    def _sp_plus_alias(self, sub):
        a = _alias_text(self.g, sub)
        return (" " + a) if a else ""

    def _join_lines(self, j, s_col):
        kw = _join_keyword(j)
        src = j.this
        on = j.args.get("on")
        indent = s_col + 2
        if isinstance(src, exp.Table):
            table_txt = self.g.sql(src)
            base = " " * indent + kw + " " + table_txt
            if on is None:
                return [base]
            conds = _conjuncts(on)
            operand_col = len(base) + 4
            return self._on_block_lines(base + " ON ", conds, operand_col)
        if isinstance(src, exp.Subquery):
            inner = src.this
            if _is_select(inner):
                paren_col = indent + len(kw) + 1
                sub_col = paren_col + 1
                lines = self.render_select(inner, sub_col)
                first = lines[0]
                out = [" " * indent + kw + " (" + first[sub_col:]]
                out.extend(lines[1:])
                out[-1] = out[-1] + ")" + self._sp_plus_alias(src)
                if on is not None:
                    conds = _conjuncts(on)
                    out.extend(self._on_block_lines(None, conds, paren_col))
                return out
            if isinstance(inner, (exp.Union, exp.Except, exp.Intersect)):
                raise _Unsupported()
            flat = self.g.sql(inner)
            alias = self._sp_plus_alias(src)
            base = " " * indent + kw + " (" + flat + ")" + alias
            if on is None:
                return [base]
            conds = _conjuncts(on)
            operand_col = len(base) + 4
            return self._on_block_lines(base + " ON ", conds, operand_col)
        raise _Unsupported()

    def _on_block_lines(self, base, conds, operand_col):
        if len(conds) == 1:
            if base is None:
                return [" " * (operand_col - 3) + "ON " + self._single_cond_text(conds[0])]
            return [base + self._single_cond_text(conds[0])]
        texts = self._cond_texts(conds, operand_col, pad_eq=True)
        if base is None:
            out = [" " * (operand_col - 3) + "ON " + texts[0]]
            for t in texts[1:]:
                out.append(" " * (operand_col - 4) + "AND " + t)
            return out
        out = [base + texts[0]]
        for t in texts[1:]:
            out.append(" " * (operand_col - 4) + "AND " + t)
        return out

    def _single_cond_text(self, c):
        if isinstance(c, exp.Paren) and isinstance(_unwrap_paren(c), exp.Or):
            return self.g.sql(c)
        return self.g.sql(_unwrap_paren(c))

    def _cond_texts(self, conds, operand_col, pad_eq):
        maxlen = 0
        lengths = []
        for c in conds:
            u = _unwrap_paren(c)
            if isinstance(u, exp.EQ) and not isinstance(_unwrap_paren(u.this), exp.Subquery) \
                    and not isinstance(_unwrap_paren(u.expression), exp.Subquery):
                lhs = self.g.sql(_unwrap_paren(u.this))
                lengths.append(len(lhs))
                maxlen = max(maxlen, len(lhs))
            else:
                lengths.append(None)
        texts = []
        for c, ln in zip(conds, lengths):
            u = _unwrap_paren(c)
            if ln is None:
                texts.append(self.g.sql(c) if isinstance(c, (exp.Paren, exp.Or, exp.And)) else self.g.sql(u))
            else:
                lhs = self.g.sql(_unwrap_paren(u.this))
                rhs = self.g.sql(_unwrap_paren(u.expression))
                if maxlen > ln:
                    lhs = lhs + " " * (maxlen - ln)
                texts.append(f"{lhs} = {rhs}")
        return texts

    def _cond_lines(self, keyword, cond, s_col, kw_col, and_col, pad_eq=False):
        conds = _conjuncts(cond)
        operand_col = kw_col + len(keyword) + 1
        texts = self._cond_texts(conds, operand_col, pad_eq)
        out = [" " * kw_col + keyword + " " + texts[0]]
        for t in texts[1:]:
            out.append(" " * and_col + "AND " + t)
        return out

    def _group_lines(self, group, s_col):
        kind = (group.args.get("kind") or "").upper()
        if kind in ("CUBE", "ROLLUP", "GROUPING SETS"):
            return [" " * (s_col + 1) + self.g.sql(group)]
        items = [self.g.sql(e) for e in group.expressions]
        if not items:
            return []
        return _pack_with_prefix("GROUP BY", items, s_col + 1, _GROUP_WRAP)

    def _having_lines(self, cond, s_col):
        conds = _disjuncts(cond)
        texts = [self.g.sql(_unwrap_paren(c)) for c in conds]
        out = [" " * s_col + "HAVING " + texts[0]]
        for t in texts[1:]:
            out.append(" " * (s_col + 4) + "OR " + t)
        return out

    def _order_lines(self, order, s_col):
        if isinstance(order, exp.Order) and order.expressions:
            items = [self.g.sql(o) for o in order.expressions]
            return [" " * (s_col + 1) + "ORDER BY " + ", ".join(items)]
        return [" " * (s_col + 1) + self.g.sql(order)]


def _flat(node):
    return _NoAsGenerator(pretty=False).sql(node)


def format_sql(sql: str) -> str:
    try:
        parsed = sqlglot.parse(sql)
        if not parsed:
            return sql
    except (ParseError, Exception):
        return sql

    gen = _CompactSQLGenerator()
    out_parts = []
    for stmt in parsed:
        try:
            lines = gen.fmt_stmt(stmt)
        except Exception:
            lines = None
        if lines is None:
            out_parts.append(_flat(stmt))
        else:
            text = "\n".join(l.rstrip() for l in lines)
            if text:
                out_parts.append(text)
    if len(out_parts) == 1:
        return out_parts[0].strip()
    if out_parts:
        return "\n\n".join(p.strip() for p in out_parts)
    return sql


class _HistoryEditor(QPlainTextEdit):
    _history_up = Signal()
    _history_down = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighter = _SQLHighlighter(self.document())

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        open_act = menu.addAction("&Abrir SQL...")
        open_act.triggered.connect(self._trigger_open_file)
        save_act = menu.addAction("&Salvar")
        save_act.triggered.connect(self._trigger_save)
        save_as_act = menu.addAction("Salvar &como...")
        save_as_act.triggered.connect(self._trigger_save_as)
        fmt_act = menu.addAction("&Formatar SQL")
        fmt_act.triggered.connect(self._trigger_format)
        bm_act = menu.addAction("Salvar como &Favorito")
        bm_act.triggered.connect(self._trigger_bookmark)
        menu.addSeparator()
        exec_act = menu.addAction("Executar (F9)")
        exec_act.triggered.connect(self._trigger_execute)
        menu.exec(event.globalPos())

    def _trigger_open_file(self):
        w = self.window()
        if hasattr(w, '_on_open_file'):
            w._on_open_file()

    def _trigger_save(self):
        w = self.window()
        if hasattr(w, 'sql_editor'):
            w.sql_editor._save_current_tab()

    def _trigger_save_as(self):
        w = self.window()
        if hasattr(w, 'sql_editor'):
            w.sql_editor._save_as_current_tab()

    def _trigger_format(self):
        w = self.window()
        if hasattr(w, 'sql_editor'):
            w.sql_editor._format_current_sql()

    def _trigger_execute(self):
        w = self.window()
        if hasattr(w, '_on_execute'):
            w._on_execute()

    def _trigger_bookmark(self):
        w = self.window()
        if hasattr(w, '_bookmarks_panel'):
            sql = self.toPlainText().strip()
            if sql:
                w._bookmarks_panel.add_bookmark(sql)

    def _indent_selection(self):
        cursor = self.textCursor()
        doc = self.document()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        sb = doc.findBlock(start_pos)
        eb = doc.findBlock(end_pos)
        sb_num = sb.blockNumber()
        eb_num = eb.blockNumber()

        cursor.beginEditBlock()
        for bn in range(sb_num, eb_num + 1):
            b = doc.findBlockByNumber(bn)
            if b.isValid():
                bc = QTextCursor(b)
                bc.movePosition(QTextCursor.StartOfBlock)
                bc.insertText("\t")
        cursor.endEditBlock()

        total_tabs = eb_num - sb_num + 1
        new_cursor = QTextCursor(doc)
        new_cursor.setPosition(start_pos + 1)
        new_cursor.setPosition(end_pos + total_tabs, QTextCursor.KeepAnchor)
        self.setTextCursor(new_cursor)

    def _unindent_selection(self):
        cursor = self.textCursor()
        doc = self.document()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()
        sb = doc.findBlock(start_pos)
        eb = doc.findBlock(end_pos)
        sb_num = sb.blockNumber()
        eb_num = eb.blockNumber()

        cursor.beginEditBlock()
        removed_at_start = 0
        total_removed = 0
        for bn in range(sb_num, eb_num + 1):
            b = doc.findBlockByNumber(bn)
            if not b.isValid():
                continue
            text = b.text()
            chars = 0
            if text.startswith("\t"):
                chars = 1
            elif text.startswith("    "):
                chars = 4
            elif text.startswith(" "):
                chars = 1
            if chars > 0:
                bc = QTextCursor(b)
                bc.movePosition(QTextCursor.StartOfBlock)
                bc.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, chars)
                bc.removeSelectedText()
                total_removed += chars
                if bn == sb_num:
                    removed_at_start = chars
        cursor.endEditBlock()

        if total_removed > 0:
            new_cursor = QTextCursor(doc)
            new_s = start_pos - removed_at_start
            new_e = end_pos - total_removed
            new_cursor.setPosition(new_s if new_s >= 0 else 0)
            new_cursor.setPosition(new_e if new_e >= new_s else new_s, QTextCursor.KeepAnchor)
            self.setTextCursor(new_cursor)

    def setPlainText(self, text):
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        cursor.beginEditBlock()
        cursor.insertText(text)
        cursor.endEditBlock()
        self.setTextCursor(QTextCursor(self.document()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Z and event.modifiers() & Qt.ControlModifier:
            if event.modifiers() & Qt.ShiftModifier:
                self.redo()
            else:
                self.undo()
            return
        if event.key() == Qt.Key_Y and event.modifiers() & Qt.ControlModifier:
            self.redo()
            return
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selection()
            else:
                cursor.insertText("\t")
            return
        if event.key() == Qt.Key_Backtab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._unindent_selection()
            return
        if event.key() == Qt.Key_Up and not self.toPlainText().strip():
            self._history_up.emit()
        elif event.key() == Qt.Key_Down and not self.toPlainText().strip():
            self._history_down.emit()
        else:
            super().keyPressEvent(event)


class FindReplaceBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_match_cursors: list[QTextCursor] = []
        self._current_match_index = -1
        self._last_search_text = ""
        self._last_case_sensitive = False
        self._built = False

    def set_editor(self, editor: QPlainTextEdit):
        self._editor = editor
        self._clear_highlights()
        self._all_match_cursors = []
        self._current_match_index = -1
        self._last_search_text = ""
        self._last_case_sensitive = False
        if not self._built:
            self._build_ui()
            self._built = True
        self.find_input.installEventFilter(self)
        self.replace_input.installEventFilter(self)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(2)

        find_row = QHBoxLayout()
        find_row.addWidget(QLabel(I18N.sql_editor["find_label"]))
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("...")
        self.find_input.setStyleSheet("padding: 2px 4px;")
        find_row.addWidget(self.find_input, 1)
        self.results_label = QLabel("")
        self.results_label.setStyleSheet("color: #888; font-size: 10px; padding: 0 4px;")
        find_row.addWidget(self.results_label)
        self.case_btn = QPushButton(I18N.sql_editor["case_sensitive"])
        self.case_btn.setCheckable(True)
        self.case_btn.setFixedWidth(28)
        self.case_btn.setFixedHeight(22)
        self.case_btn.setStyleSheet("font-size: 10px; padding: 1px;")
        find_row.addWidget(self.case_btn)
        self.close_btn = QPushButton("\u00d7")
        self.close_btn.setFixedWidth(22)
        self.close_btn.setFixedHeight(22)
        self.close_btn.setToolTip(I18N.sql_editor["close_find"])
        find_row.addWidget(self.close_btn)
        layout.addLayout(find_row)

        self._replace_row_widget = QWidget()
        replace_row = QHBoxLayout(self._replace_row_widget)
        replace_row.setContentsMargins(0, 0, 0, 0)
        replace_row.addWidget(QLabel(I18N.sql_editor["replace_label"]))
        self.replace_input = QLineEdit()
        self.replace_input.setStyleSheet("padding: 2px 4px;")
        replace_row.addWidget(self.replace_input, 1)
        self.replace_btn = QPushButton(I18N.sql_editor["replace_btn"])
        self.replace_btn.setFixedHeight(22)
        self.replace_btn.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        replace_row.addWidget(self.replace_btn)
        self.replace_all_btn = QPushButton(I18N.sql_editor["replace_all"])
        self.replace_all_btn.setFixedHeight(22)
        self.replace_all_btn.setStyleSheet("font-size: 10px; padding: 1px 6px;")
        replace_row.addWidget(self.replace_all_btn)
        layout.addWidget(self._replace_row_widget)

        self.find_input.textChanged.connect(self._on_text_changed)
        self.find_input.returnPressed.connect(self._find_next_from_input)
        self.case_btn.toggled.connect(self._on_text_changed)
        self.close_btn.clicked.connect(self._hide)
        self.replace_btn.clicked.connect(self._replace_current)
        self.replace_all_btn.clicked.connect(self._replace_all)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            mod = event.modifiers()
            if key == Qt.Key_Escape:
                self._hide()
                self._editor.setFocus()
                return True
            if key == Qt.Key_Return and mod & Qt.ShiftModifier:
                self._find_previous()
                return True
            if key == Qt.Key_F3 and not (mod & Qt.ShiftModifier):
                self._find_next()
                return True
            if key == Qt.Key_F3 and mod & Qt.ShiftModifier:
                self._find_previous()
                return True
            if key == Qt.Key_Tab and obj == self.find_input:
                self.replace_input.setFocus()
                self.replace_input.selectAll()
                return True
        return super().eventFilter(obj, event)

    def _hide(self):
        self.setVisible(False)
        self._clear_highlights()

    def _clear_highlights(self):
        self._editor.setExtraSelections([])

    def show_find_mode(self):
        self._replace_row_widget.setVisible(False)
        self.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._restore_search()

    def show_replace_mode(self):
        self._replace_row_widget.setVisible(True)
        self.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._restore_search()

    def _restore_search(self):
        if self._last_search_text:
            self.find_input.setText(self._last_search_text)
            self.case_btn.setChecked(self._last_case_sensitive)
            self._on_text_changed()

    def _on_text_changed(self):
        text = self.find_input.text()
        self._last_search_text = text
        self._last_case_sensitive = self.case_btn.isChecked()
        self._highlight_matches()

    def _get_find_flags(self):
        return QTextDocument.FindCaseSensitively if self.case_btn.isChecked() else QTextDocument.FindFlag()

    def _filter_sql_quotes(self, matches: list) -> list:
        """Filter out ' matches that are part of '' (SQL escaped quote)."""
        if self.find_input.text() != "'":
            return matches
        doc_text = self._editor.toPlainText()
        result = []
        for m in matches:
            pos = m.selectionStart() if hasattr(m, 'selectionStart') else m[0]
            if not (pos + 1 < len(doc_text) and doc_text[pos] == "'" and doc_text[pos + 1] == "'"):
                result.append(m)
        return result

    def _highlight_matches(self):
        self._all_match_cursors = []
        text = self.find_input.text()
        if not text:
            self._editor.setExtraSelections([])
            self.results_label.setText("")
            return

        doc = self._editor.document()
        flags = self._get_find_flags()
        cursor = QTextCursor(doc)

        while True:
            found = doc.find(text, cursor, flags)
            if found.isNull():
                break
            self._all_match_cursors.append(QTextCursor(found))
            cursor = found

        self._all_match_cursors = self._filter_sql_quotes(self._all_match_cursors)
        count = len(self._all_match_cursors)
        if count > 0:
            self.results_label.setText(I18N.sql_editor["results_count"].format(n=count))
            self.results_label.setStyleSheet("color: #107c10; font-size: 10px; padding: 0 4px;")
        else:
            self.results_label.setText(I18N.sql_editor["no_results"])
            self.results_label.setStyleSheet("color: #d32f2f; font-size: 10px; padding: 0 4px;")

        selections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffff99"))

        current_fmt = QTextCharFormat()
        current_fmt.setBackground(QColor("#ffcc00"))

        for i, mc in enumerate(self._all_match_cursors):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = mc
            sel.format = current_fmt if i == self._current_match_index else fmt
            selections.append(sel)

        self._editor.setExtraSelections(selections)

    def _find_next_from_input(self):
        self._current_match_index = -1
        self._find_next()

    def _find_next(self):
        text = self.find_input.text()
        if not text:
            return
        if self._all_match_cursors:
            self._current_match_index = (self._current_match_index + 1) % len(self._all_match_cursors)
            cursor = self._all_match_cursors[self._current_match_index]
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()
            self._highlight_matches()
        else:
            self._current_match_index = -1
            self._highlight_matches()

    def _find_previous(self):
        text = self.find_input.text()
        if not text:
            return
        if self._all_match_cursors:
            self._current_match_index = (self._current_match_index - 1) % len(self._all_match_cursors)
            cursor = self._all_match_cursors[self._current_match_index]
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()
            self._highlight_matches()
        else:
            self._current_match_index = -1
            self._highlight_matches()

    def find_next_global(self):
        self._find_next()

    def find_previous_global(self):
        self._find_previous()

    def _replace_current(self):
        text = self.find_input.text()
        if not text or not self._all_match_cursors:
            return

        if self._current_match_index < 0 or self._current_match_index >= len(self._all_match_cursors):
            self._current_match_index = 0

        cursor = self._all_match_cursors[self._current_match_index]
        replacement = self.replace_input.text()
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(replacement)
        cursor.endEditBlock()

        self._on_text_changed()
        self._find_next()

    def _replace_all(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text or text == replacement:
            return

        flags = self._get_find_flags()
        doc = self._editor.document()

        positions: list[tuple[int, int]] = []
        cursor = QTextCursor(doc)
        while True:
            found = doc.find(text, cursor, flags)
            if found.isNull():
                break
            positions.append((found.selectionStart(), found.selectionEnd() - found.selectionStart()))
            cursor.setPosition(found.selectionEnd())

        positions = self._filter_sql_quotes(positions)

        if not positions:
            return

        edit_cursor = QTextCursor(doc)
        edit_cursor.beginEditBlock()
        for pos, length in reversed(positions):
            c = QTextCursor(doc)
            c.setPosition(pos)
            c.setPosition(pos + length, QTextCursor.KeepAnchor)
            c.removeSelectedText()
            c.insertText(replacement)
        edit_cursor.endEditBlock()

        self._current_match_index = -1
        self.find_input.setText(text)


_TAB_EDITOR_STYLE = """
    QPlainTextEdit {
        background-color: #1e1e1e;
        color: #d4d4d4;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 8px;
    }
"""


class SQLEditor(QWidget):
    execute_clicked = Signal()
    import_csv_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tabs: list[dict] = []
        self._tab_counter = 0
        self._build_ui()
        self._add_tab()
        self._search_bar.setVisible(False)

    def _rename_tab(self, idx: int):
        if 0 > idx >= len(self._tabs):
            return
        old_name = self.tab_widget.tabText(idx)
        new_name, ok = QInputDialog.getText(
            self, "Renomear Aba", "Novo nome:",
            text=old_name
        )
        if ok and new_name.strip():
            self.tab_widget.setTabText(idx, new_name.strip())

    def _save_current_tab(self):
        info = self._current_tab()
        content = info["editor"].toPlainText()
        file_path = info.get("file_path", "")
        if not file_path:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Salvar SQL", "", "Arquivos SQL (*.sql);;Todos (*)"
            )
            if not file_path:
                return
            info["file_path"] = file_path
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.tab_widget.setTabText(
                self.tab_widget.currentIndex(),
                info.get("tab_name", "") or file_path.split("\\")[-1]
            )
        except Exception as e:
            show_critical(self, "Erro ao Salvar", str(e))

    def _save_as_current_tab(self):
        info = self._current_tab()
        content = info["editor"].toPlainText()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar SQL como...", "", "Arquivos SQL (*.sql);;Todos (*)"
        )
        if not file_path:
            return
        info["file_path"] = file_path
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.tab_widget.setTabText(
                self.tab_widget.currentIndex(),
                file_path.split("\\")[-1]
            )
        except Exception as e:
            show_critical(self, "Erro ao Salvar", str(e))

    def _make_editor(self) -> _HistoryEditor:
        e = _HistoryEditor()
        e.setFont(QFont("Consolas", 10))
        e.setTabStopDistance(20)
        e.setLineWrapMode(QPlainTextEdit.NoWrap)
        e.setPlaceholderText(I18N.sql_editor["placeholder"])
        e.setStyleSheet(_TAB_EDITOR_STYLE)
        return e

    def _current_tab(self) -> dict:
        idx = self.tab_widget.currentIndex()
        if 0 <= idx < len(self._tabs):
            return self._tabs[idx]
        return self._tabs[0]

    def _current_editor(self) -> _HistoryEditor:
        return self._current_tab()["editor"]

    def _on_tab_changed(self, idx: int):
        if 0 <= idx < len(self._tabs):
            self._search_bar.set_editor(self._tabs[idx]["editor"])

    def add_tab(self, tab_name: str, content: str):
        self._tab_counter += 1
        editor = self._make_editor()
        editor.setPlainText(content)
        info = {"editor": editor, "history": [], "history_index": -1,
                "tab_name": tab_name, "file_path": ""}
        self._tabs.append(info)
        idx = self.tab_widget.addTab(editor, tab_name)
        self.tab_widget.setCurrentIndex(idx)
        tab_bar = self.tab_widget.tabBar()
        if len(self._tabs) > 1:
            tab_bar.setTabButton(idx - 1, QTabBar.RightSide, None)
        tab_bar.setTabButton(idx, QTabBar.RightSide,
                             self._make_close_btn(idx))
        editor._history_up.connect(lambda t=info: self._history_up_for(t))
        editor._history_down.connect(lambda t=info: self._history_down_for(t))
        self._search_bar.set_editor(editor)
        editor.setFocus()

    def _add_tab(self, content: str = ""):
        self._tab_counter += 1
        editor = self._make_editor()
        if content:
            editor.setPlainText(content)

        tab_name = f"SQL {self._tab_counter}"
        info = {"editor": editor, "history": [], "history_index": -1,
                "tab_name": tab_name, "file_path": ""}
        self._tabs.append(info)

        idx = self.tab_widget.addTab(editor, tab_name)
        self.tab_widget.setCurrentIndex(idx)

        tab_bar = self.tab_widget.tabBar()
        if len(self._tabs) > 1:
            tab_bar.setTabButton(idx - 1, QTabBar.RightSide, None)
        tab_bar.setTabButton(idx, QTabBar.RightSide,
                             self._make_close_btn(idx))

        editor._history_up.connect(lambda t=info: self._history_up_for(t))
        editor._history_down.connect(lambda t=info: self._history_down_for(t))
        self._search_bar.set_editor(editor)
        editor.setFocus()

    def _make_close_btn(self, idx: int):
        btn = QToolButton()
        btn.setText("\u00d7")
        btn.setAutoRaise(True)
        btn.clicked.connect(lambda: self._close_tab(idx))
        btn.setStyleSheet("QToolButton { border: none; padding: 1px 4px; }")
        return btn

    def _refresh_close_buttons(self):
        tb = self.tab_widget.tabBar()
        for i in range(tb.count()):
            tb.setTabButton(i, QTabBar.RightSide,
                            self._make_close_btn(i) if len(self._tabs) > 1 else None)

    def _close_tab(self, idx: int):
        if len(self._tabs) <= 1:
            return
        self.tab_widget.removeTab(idx)
        self._tabs.pop(idx)
        self._refresh_close_buttons()
        if self.tab_widget.currentIndex() >= 0:
            self._on_tab_changed(self.tab_widget.currentIndex())

    @staticmethod
    def _make_play_icon() -> QIcon:
        pm = QPixmap(28, 28)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        poly = QPolygon([QPoint(8, 5), QPoint(23, 14), QPoint(8, 23)])
        p.drawPolygon(poly)
        p.end()
        return QIcon(pm)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        label = QLabel(I18N.sql_editor["command_label"])
        label.setStyleSheet("font-weight: bold;")
        self.rows_label = QLabel("")
        self.rows_label.setStyleSheet("color: #888;")
        header.addWidget(label)
        header.addStretch()
        header.addWidget(self.rows_label)
        layout.addLayout(header)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabBarDoubleClicked.connect(
            lambda idx: self._rename_tab(idx) if idx >= 0 else None
        )

        add_btn = QToolButton()
        add_btn.setText("+")
        add_btn.setAutoRaise(True)
        add_btn.clicked.connect(lambda: self._add_tab())
        add_btn.setToolTip("Nova aba")
        add_btn.setStyleSheet("QToolButton { border: none; padding: 2px 8px; font-weight: bold; }")
        self.tab_widget.setCornerWidget(add_btn, Qt.TopRightCorner)

        layout.addWidget(self.tab_widget, 1)

        self._search_bar = FindReplaceBar(self)
        layout.addWidget(self._search_bar)

        self.import_btn = QPushButton(I18N.sql_editor["import_csv"])
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; padding: 8px 16px;
                font-weight: bold; font-size: 11px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.import_csv_clicked.emit)

        self.execute_btn = QPushButton(I18N.sql_editor["execute"])
        self.execute_btn.setIcon(self._make_play_icon())
        self.execute_btn.setIconSize(QSize(16, 16))
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 8px 16px;
                font-weight: bold; font-size: 11px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b6b0b; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.execute_btn.setEnabled(False)
        self.execute_btn.clicked.connect(self.execute_clicked.emit)

        self._btn_layout = QHBoxLayout()
        self._btn_layout.addWidget(self.import_btn)
        self._btn_layout.addStretch()
        self._btn_layout.addWidget(self.execute_btn)
        layout.addLayout(self._btn_layout)

    def add_left_button(self, btn: QPushButton) -> None:
        idx = self._btn_layout.count() - 1
        self._btn_layout.insertWidget(idx, btn)

    def set_connected(self, connected: bool):
        self.execute_btn.setEnabled(connected)
        self.import_btn.setEnabled(connected)

    def set_rows_affected(self, rows: int):
        self.rows_label.setText(I18N.sql_editor["rows_affected"].format(n=rows))

    def set_rows_returned(self, rows: int):
        self.rows_label.setText(I18N.sql_editor["rows_returned"].format(n=rows))

    def clear_status(self):
        self.rows_label.setText("")

    def get_sql(self) -> str:
        editor = self._current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            raw = cursor.selectedText()
            raw = raw.replace('\u2029', '\n')
        else:
            raw = editor.toPlainText()
        return strip_sql_comments(raw)

    def focus_sql(self):
        self._current_editor().setFocus()

    def add_to_history(self, sql: str) -> None:
        info = self._current_tab()
        if not sql:
            return
        if info["history"] and info["history"][-1] == sql:
            return
        info["history"].append(sql)
        if len(info["history"]) > 100:
            info["history"].pop(0)
        info["history_index"] = len(info["history"])

    def _history_up_for(self, info: dict):
        if not info["history"]:
            return
        if info["history_index"] > 0:
            info["history_index"] -= 1
            info["editor"].setPlainText(info["history"][info["history_index"]])

    def _history_down_for(self, info: dict):
        if not info["history"]:
            return
        if info["history_index"] < len(info["history"]) - 1:
            info["history_index"] += 1
            info["editor"].setPlainText(info["history"][info["history_index"]])
        else:
            info["history_index"] = len(info["history"])
            info["editor"].clear()

    def show_find(self):
        self._search_bar.show_find_mode()
        self._search_bar.find_input.setFocus()

    def show_replace(self):
        self._search_bar.show_replace_mode()
        self._search_bar.find_input.setFocus()

    def hide_search(self):
        self._search_bar._hide()

    def is_search_visible(self) -> bool:
        return self._search_bar.isVisible()

    def find_next(self):
        self._search_bar.find_next_global()

    def find_previous(self):
        self._search_bar.find_previous_global()

    def _format_current_sql(self):
        editor = self._current_editor()
        sql = editor.toPlainText()
        formatted = format_sql(sql)
        if formatted != sql:
            editor.setPlainText(formatted)
