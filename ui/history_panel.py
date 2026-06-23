import csv
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont


class HistoryPanel(QWidget):
    load_query_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Histórico")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()

        self._refresh_btn = QPushButton("Atualizar")
        self._refresh_btn.setFixedHeight(24)
        self._refresh_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)
        layout.addLayout(header)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filtrar histórico...")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(self.refresh)
        layout.addWidget(self._filter_edit)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Data/Hora", "Status", "Linhas", "ms", "SQL"])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._table.setSortingEnabled(True)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        layout.addWidget(self._table)

    def refresh(self):
        filter_text = self._filter_edit.text().strip().lower()
        rows = self._load_history()
        if filter_text:
            rows = [r for r in rows if filter_text in r[4].lower()]

        self._table.setRowCount(len(rows))
        for i, (ts, status, rowcount, duration, sql) in enumerate(rows):
            ts_item = QTableWidgetItem(ts)
            ts_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 0, ts_item)

            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if status == "OK":
                status_item.setForeground(QColor("#107c10"))
            else:
                status_item.setForeground(QColor("#d32f2f"))
            self._table.setItem(i, 1, status_item)

            rc_item = QTableWidgetItem(str(rowcount))
            rc_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 2, rc_item)

            dur_item = QTableWidgetItem(str(duration))
            dur_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(i, 3, dur_item)

            sql_item = QTableWidgetItem(sql)
            sql_item.setToolTip(sql)
            font = QFont("Consolas", 9)
            sql_item.setFont(font)
            self._table.setItem(i, 4, sql_item)

        self._table.resizeRowsToContents()

    def _load_history(self) -> list[tuple[str, str, int, int, str]]:
        rows: list[tuple[str, str, int, int, str]] = []
        log_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "logs" / "query_log.csv"
        log_path = log_path.resolve()
        if log_path.exists():
            try:
                with open(log_path, encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 6:
                            ts, server, db, sql, success, rest = row[0], row[1], row[2], row[3], row[4], ",".join(row[5:])
                            try:
                                rcount, duration = rest.split(",", 1)
                            except ValueError:
                                rcount, duration = "0", "0"
                            status = "OK" if success.lower() == "true" else "ERRO"
                            try:
                                rc_int = int(rcount)
                            except ValueError:
                                rc_int = 0
                            try:
                                dur_int = int(duration)
                            except ValueError:
                                dur_int = 0
                            rows.append((ts, status, rc_int, dur_int, sql))
            except (OSError, csv.Error):
                pass
        rows.reverse()
        return rows[:500]

    def _on_item_double_clicked(self, item):
        row = item.row()
        sql_item = self._table.item(row, 4)
        if sql_item and sql_item.text():
            self.load_query_requested.emit(sql_item.text())
