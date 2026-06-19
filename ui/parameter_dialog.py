from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from infrastructure.i18n import I18N


class ParameterDialog(QDialog):
    def __init__(self, param_names: list[str], parent=None, last_values: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(I18N.parameter_dialog["title"])
        self.setMinimumSize(450, 200)
        self.resize(500, 250)
        self._param_names = param_names
        self._values: dict[str, str] = {}
        if last_values:
            self._values.update(last_values)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(len(self._param_names), 2)
        self.table.setHorizontalHeaderLabels([
            I18N.parameter_dialog["param_column"],
            I18N.parameter_dialog["value_column"],
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setFont(QFont("Consolas", 10))

        for i, name in enumerate(self._param_names):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item)

            val = self._values.get(name, "")
            value_item = QTableWidgetItem(val)
            self.table.setItem(i, 1, value_item)

        self.table.setCurrentCell(0, 1)
        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton(I18N.parameter_dialog["ok"])
        ok_btn.setStyleSheet("""
            QPushButton { background-color: #107c10; color: white; padding: 6px 24px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #0b6b0b; }
        """)
        ok_btn.clicked.connect(self._accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton(I18N.parameter_dialog["cancel"])
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: #888; color: white; padding: 6px 24px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #666; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _accept(self):
        for i in range(self.table.rowCount()):
            name = self._param_names[i]
            item = self.table.item(i, 1)
            self._values[name] = item.text().strip() if item else ""
        self.accept()

    def get_values(self) -> dict[str, str]:
        return dict(self._values)
