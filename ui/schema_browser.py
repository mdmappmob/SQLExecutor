from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from infrastructure.i18n import I18N
from domain.interfaces import DatabaseAdapter


class SchemaBrowser(QWidget):
    item_insert_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._adapter: DatabaseAdapter | None = None
        self._build_ui()

    def set_adapter(self, adapter: DatabaseAdapter | None):
        self._adapter = adapter
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Navegador")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()

        self._refresh_btn = QPushButton("Atualizar")
        self._refresh_btn.setFixedHeight(24)
        self._refresh_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self._refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setAlternatingRowColors(True)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree)

    def refresh(self):
        self._tree.clear()
        if not self._adapter or not self._adapter.is_connected():
            item = QTreeWidgetItem(["Desconectado"])
            item.setForeground(0, Qt.gray)
            self._tree.addTopLevelItem(item)
            return

        try:
            schema = self._adapter.get_schema()
        except Exception:
            item = QTreeWidgetItem(["Erro ao carregar schema"])
            item.setForeground(0, Qt.red)
            self._tree.addTopLevelItem(item)
            return

        type_order = {"TABLE": 0, "VIEW": 1, "PROCEDURE": 2}
        groups: dict[str, list] = {}
        for t in schema:
            groups.setdefault(t.type, []).append(t)

        sorted_types = sorted(groups.keys(), key=lambda x: type_order.get(x, 99))

        for obj_type in sorted_types:
            items = groups[obj_type]
            group_item = QTreeWidgetItem([obj_type])
            group_item.setData(0, Qt.UserRole, "__group__")
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            group_item.setExpanded(True)
            self._tree.addTopLevelItem(group_item)

            for table_info in sorted(items, key=lambda x: x.name.lower()):
                table_item = QTreeWidgetItem([table_info.name])
                table_item.setData(0, Qt.UserRole, table_info.name)
                table_item.setToolTip(0, f"{table_info.type}: {table_info.name}")
                group_item.addChild(table_item)

                for col in table_info.columns:
                    col_text = col.name
                    badges = []
                    if col.is_pk:
                        badges.append("PK")
                    col_text += f"  ({col.data_type}"
                    if badges:
                        col_text += f", {', '.join(badges)}"
                    col_text += ")"
                    col_item = QTreeWidgetItem([col_text])
                    col_item.setData(0, Qt.UserRole, col.name)
                    col_item.setToolTip(0, f"{col.name} ({col.data_type})")
                    col_item.setForeground(0, Qt.darkGray)
                    table_item.addChild(col_item)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int):
        data = item.data(0, Qt.UserRole)
        if data and data != "__group__":
            self.item_insert_requested.emit(data)

    def focus_filter(self):
        self._tree.setFocus()
