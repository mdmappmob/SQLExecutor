from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel,
    QLineEdit, QTextEdit, QTabWidget, QToolButton, QTabBar,
    QInputDialog, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QEvent, QPoint, QSize
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument, QColor, QShortcut, QKeySequence, QIcon, QPixmap, QPolygon, QBrush, QPen, QPainter

from infrastructure.i18n import I18N


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


def format_sql(sql: str) -> str:
    from sqlglot import transpile
    from sqlglot.errors import ParseError
    try:
        result = transpile(
            sql,
            pretty=True,
            error_level=None,
        )
        if result:
            return result[0].strip()
    except (ParseError, Exception):
        pass
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

    def keyPressEvent(self, event):
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
            QMessageBox.critical(self, "Erro ao Salvar", str(e))

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
            QMessageBox.critical(self, "Erro ao Salvar", str(e))

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
                font-weight: bold; font-size: 10px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self.import_csv_clicked.emit)

        self.execute_btn = QPushButton(I18N.sql_editor["execute"])
        self.execute_btn.setIcon(self._make_play_icon())
        self.execute_btn.setIconSize(QSize(24, 24))
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 8px 20px;
                font-weight: bold; font-size: 12px; border-radius: 4px;
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
