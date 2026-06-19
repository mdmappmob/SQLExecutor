from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel,
    QLineEdit, QTextEdit
)
from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument, QColor

from infrastructure.i18n import I18N


class _SQLCommentHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self._fmt = QTextCharFormat()
        self._fmt.setFontItalic(True)

    def highlightBlock(self, text):
        n = len(text)
        state = self.previousBlockState()

        if state == 1:
            end = text.find('*/')
            if end >= 0:
                self.setFormat(0, end + 2, self._fmt)
                self.setCurrentBlockState(0)
                text = text[end + 2:]
            else:
                self.setFormat(0, n, self._fmt)
                self.setCurrentBlockState(1)
                return

        i = 0
        m = len(text)
        while i < m:
            if text[i:i + 2] == '/*':
                end = text.find('*/', i + 2)
                if end == -1:
                    self.setFormat(i, m - i, self._fmt)
                    self.setCurrentBlockState(1)
                    return
                self.setFormat(i, end - i + 2, self._fmt)
                i = end + 2
            elif text[i:i + 2] == '--':
                self.setFormat(i, m - i, self._fmt)
                self.setCurrentBlockState(0)
                return
            else:
                i += 1

        self.setCurrentBlockState(0)


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


class _HistoryEditor(QPlainTextEdit):
    _history_up = Signal()
    _history_down = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlighter = _SQLCommentHighlighter(self.document())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up and not self.toPlainText().strip():
            self._history_up.emit()
        elif event.key() == Qt.Key_Down and not self.toPlainText().strip():
            self._history_down.emit()
        else:
            super().keyPressEvent(event)


class FindReplaceBar(QWidget):
    def __init__(self, editor: QPlainTextEdit, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._all_match_cursors: list[QTextCursor] = []
        self._current_match_index = -1
        self._last_search_text = ""
        self._last_case_sensitive = False
        self._build_ui()
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
            if key == Qt.Key_F3:
                self._find_next()
                return True
            if key == Qt.Key_F3 and mod & Qt.ShiftModifier:
                self._find_previous()
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
        if not text or self._current_match_index < 0 or self._current_match_index >= len(self._all_match_cursors):
            return

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


class SQLEditor(QWidget):
    execute_clicked = Signal()
    import_csv_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1
        self._build_ui()
        self._search_bar.setVisible(False)

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

        self.editor = _HistoryEditor()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setTabStopDistance(20)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setPlaceholderText(I18N.sql_editor["placeholder"])
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.editor._history_up.connect(self._history_up)
        self.editor._history_down.connect(self._history_down)
        layout.addWidget(self.editor, 1)

        self._search_bar = FindReplaceBar(self.editor, self)
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
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 8px 30px;
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
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            raw = cursor.selectedText()
            raw = raw.replace('\u2029', '\n')
        else:
            raw = self.editor.toPlainText()
        cleaned = strip_sql_comments(raw)
        return cleaned

    def focus_sql(self):
        self.editor.setFocus()

    def add_to_history(self, sql: str) -> None:
        if not sql:
            return
        if self._history and self._history[-1] == sql:
            return
        self._history.append(sql)
        if len(self._history) > 100:
            self._history.pop(0)
        self._history_index = len(self._history)

    def _history_up(self):
        if not self._history:
            return
        if self._history_index > 0:
            self._history_index -= 1
            self.editor.setPlainText(self._history[self._history_index])

    def _history_down(self):
        if not self._history:
            return
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.editor.setPlainText(self._history[self._history_index])
        else:
            self._history_index = len(self._history)
            self.editor.clear()

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
