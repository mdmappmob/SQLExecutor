from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat

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


class SQLEditor(QWidget):
    execute_clicked = Signal()
    import_csv_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
        layout.addWidget(self.editor)

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
