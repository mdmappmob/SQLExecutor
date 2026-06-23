from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QMessageBox, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from domain.dialect.translator import translate
from infrastructure.i18n import I18N
from infrastructure.adapters.db_types import DBType


class TranslateDialog(QDialog):
    def __init__(self, source_db_type: str, sql: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Traduzir SQL")
        self.setMinimumSize(700, 400)
        self.resize(750, 450)
        self._sql = sql
        self._source_db = source_db_type
        self._result_sql = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Dialeto de origem:"))
        self._source_combo = QComboBox()
        selector_layout.addWidget(self._source_combo)
        selector_layout.addSpacing(20)
        selector_layout.addWidget(QLabel("Dialeto de destino:"))
        self._target_combo = QComboBox()
        selector_layout.addWidget(self._target_combo)
        selector_layout.addStretch()
        layout.addLayout(selector_layout)

        self._input_editor = QTextEdit()
        self._input_editor.setPlainText(self._sql)
        self._input_editor.setFont(QFont("Consolas", 10))
        self._input_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #333; padding: 6px;
            }
        """)
        layout.addWidget(QLabel("SQL de origem:"))
        layout.addWidget(self._input_editor, 1)

        self._translate_btn = QPushButton("Traduzir")
        self._translate_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: white; padding: 8px 24px;
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #106ebe; }
        """)
        self._translate_btn.clicked.connect(self._on_translate)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self._translate_btn)
        layout.addLayout(btn_layout)

        self._output_editor = QTextEdit()
        self._output_editor.setReadOnly(True)
        self._output_editor.setFont(QFont("Consolas", 10))
        self._output_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #333; padding: 6px;
            }
        """)
        layout.addWidget(QLabel("SQL traduzido:"))
        layout.addWidget(self._output_editor, 1)

        action_layout = QHBoxLayout()
        self._use_btn = QPushButton("Usar tradução")
        self._use_btn.setEnabled(False)
        self._use_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10; color: white; padding: 8px 24px;
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0b6b0b; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self._use_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #888; color: white; padding: 8px 24px;
                font-weight: bold; border-radius: 4px;
            }
            QPushButton:hover { background-color: #666; }
        """)
        cancel_btn.clicked.connect(self.reject)

        action_layout.addStretch()
        action_layout.addWidget(self._use_btn)
        action_layout.addWidget(cancel_btn)
        layout.addLayout(action_layout)

        self._populate_combos()

    def _populate_combos(self):
        for value, label in DBType.choices():
            self._source_combo.addItem(label, value)
            self._target_combo.addItem(label, value)

        idx = self._source_combo.findData(self._source_db)
        if idx >= 0:
            self._source_combo.setCurrentIndex(idx)

        default_target = "oracle" if self._source_db == "mssql" else "mssql"
        idx = self._target_combo.findData(default_target)
        if idx >= 0:
            self._target_combo.setCurrentIndex(idx)

    def _on_translate(self):
        source = self._source_combo.currentData()
        target = self._target_combo.currentData()
        sql = self._input_editor.toPlainText().strip()

        if not sql:
            QMessageBox.warning(self, "Traduzir SQL", "Digite o SQL de origem.")
            return
        if source == target:
            QMessageBox.information(self, "Traduzir SQL", "Origem e destino são iguais.")
            return

        try:
            result = translate(sql, source, target)
            self._output_editor.setPlainText(result)
            self._result_sql = result
            self._use_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Erro na tradução", str(e))

    def get_result(self) -> str:
        return self._result_sql
