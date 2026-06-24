from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QHeaderView, QApplication, QMenu, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QAction

from infrastructure.i18n import I18N
from domain.interfaces import DatabaseAdapter, TableInfo


class SchemaBrowser(QWidget):
    item_insert_requested = Signal(str)
    script_generated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._adapter: DatabaseAdapter | None = None
        self._db_type = "mssql"
        self._schema_data: list[TableInfo] = []
        self._build_ui()

    def set_adapter(self, adapter: DatabaseAdapter | None):
        self._adapter = adapter
        self.refresh()

    def set_db_type(self, db_type: str):
        self._db_type = db_type

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
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree)

        self._overlay = QFrame(self._tree)
        self._overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 30, 180);
                border-radius: 10px;
            }
        """)
        self._overlay_layout = QVBoxLayout(self._overlay)
        self._overlay_layout.setAlignment(Qt.AlignCenter)

        self._overlay_label = QLabel("Carregando...")
        self._overlay_label.setAlignment(Qt.AlignCenter)
        self._overlay_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; background: transparent;")
        self._overlay_layout.addWidget(self._overlay_label)

        self._overlay.hide()

    def _center_overlay(self):
        if self._overlay.isVisible():
            tree_rect = self._tree.contentsRect()
            overlay_w = min(280, tree_rect.width() - 20)
            overlay_h = 80
            x = (tree_rect.width() - overlay_w) // 2
            y = (tree_rect.height() - overlay_h) // 2
            self._overlay.setGeometry(x, y, overlay_w, overlay_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._center_overlay()

    def _show_overlay(self, text: str = "Carregando..."):
        self._overlay_label.setText(text)
        self._overlay.show()
        self._center_overlay()
        self._tree.setVisible(True)
        QApplication.processEvents()

    def _hide_overlay(self):
        self._overlay.hide()

    def refresh(self):
        self._tree.clear()
        if not self._adapter or not self._adapter.is_connected():
            item = QTreeWidgetItem(["Desconectado"])
            item.setForeground(0, Qt.gray)
            self._tree.addTopLevelItem(item)
            return

        self._show_overlay("Carregando schema...")
        self._refresh_btn.setEnabled(False)

        QTimer.singleShot(50, self._do_load)

    def _do_load(self):
        schema = None
        error_msg = ""
        try:
            schema = self._adapter.get_schema()
        except Exception as e:
            error_msg = str(e)
        finally:
            self._hide_overlay()
            self._refresh_btn.setEnabled(True)

        self._schema_data = schema or []

        if error_msg:
            item = QTreeWidgetItem([f"Erro: {error_msg}"])
            item.setForeground(0, Qt.red)
            self._tree.addTopLevelItem(item)
            return

        if not schema:
            item = QTreeWidgetItem(["Nenhuma tabela encontrada"])
            item.setForeground(0, Qt.gray)
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

                for fk in table_info.foreign_keys:
                    fk_text = f"  FK {fk.fk_name or ''}: {fk.column} -> {fk.ref_table}({fk.ref_column})"
                    fk_item = QTreeWidgetItem([fk_text])
                    fk_item.setForeground(0, QColor("#8B4513"))
                    fk_item.setToolTip(0, f"FK: {fk.fk_name}")
                    table_item.addChild(fk_item)

                for idx in table_info.indexes:
                    idx_cols = ", ".join(idx.columns)
                    unique = "UNIQUE " if idx.is_unique else ""
                    idx_text = f"  {unique}INDEX {idx.name} ({idx_cols})"
                    idx_item = QTreeWidgetItem([idx_text])
                    idx_item.setForeground(0, QColor("#2E8B57"))
                    idx_item.setToolTip(0, f"Index: {idx.name}")
                    table_item.addChild(idx_item)

    def _quote_identifier(self, name: str) -> str:
        if self._db_type == "mssql":
            return f"[{name}]"
        if self._db_type in ("mysql", "mariadb"):
            return f"`{name}`"
        return f'"{name}"'

    def _find_table_info(self, name: str) -> TableInfo | None:
        for t in self._schema_data:
            if t.name == name:
                return t
        return None

    def _generate_create_table(self, table_info: TableInfo) -> str:
        lines = [f"CREATE TABLE {self._quote_identifier(table_info.name)} ("]
        col_lines = []
        pk_cols = []

        for col in table_info.columns:
            nullable = " NOT NULL" if not col.nullable else ""
            if col.is_pk:
                pk_cols.append(self._quote_identifier(col.name))
            col_lines.append(f"    {self._quote_identifier(col.name)} {col.data_type}{nullable}")

        constraint_lines = []
        if pk_cols:
            constraint_lines.append(f"    CONSTRAINT PK_{table_info.name} PRIMARY KEY ({', '.join(pk_cols)})")

        for fk in table_info.foreign_keys:
            name = fk.fk_name if fk.fk_name else f"FK_{table_info.name}_{fk.column}"
            constraint_lines.append(
                f"    CONSTRAINT {name} FOREIGN KEY ({self._quote_identifier(fk.column)}) "
                f"REFERENCES {self._quote_identifier(fk.ref_table)}({self._quote_identifier(fk.ref_column)})"
            )

        all_body = col_lines[:]
        if constraint_lines:
            all_body[-1] = all_body[-1] + ","
            all_body.extend(constraint_lines)
        lines.extend(all_body)
        lines.append(");")

        if table_info.indexes:
            lines.append("")
            for idx in table_info.indexes:
                unique = "UNIQUE " if idx.is_unique else ""
                idx_cols = ", ".join(self._quote_identifier(c) for c in idx.columns)
                lines.append(
                    f"CREATE {unique}INDEX {idx.name} "
                    f"ON {self._quote_identifier(table_info.name)}({idx_cols});"
                )

        return "\n".join(lines)

    def _generate_drop_table(self, table_info: TableInfo) -> str:
        lines = []
        for fk in table_info.foreign_keys:
            name = fk.fk_name if fk.fk_name else f"FK_{table_info.name}_{fk.column}"
            lines.append(
                f"ALTER TABLE {self._quote_identifier(table_info.name)} "
                f"DROP CONSTRAINT {name};"
            )
        lines.append(f"DROP TABLE IF EXISTS {self._quote_identifier(table_info.name)};")
        return "\n".join(lines)

    def _generate_select(self, table_info: TableInfo) -> str:
        cols = ", ".join(
            self._quote_identifier(c.name) for c in table_info.columns
        )
        return f"SELECT {cols} FROM {self._quote_identifier(table_info.name)};"

    def _on_tree_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not item:
            return
        name = item.data(0, Qt.UserRole)
        if not name or name == "__group__":
            return
        table_info = self._find_table_info(name)
        if not table_info:
            return
        if table_info.type == "VIEW":
            menu = QMenu(self)
            select_action = QAction("Gerar SELECT *", self)
            select_action.triggered.connect(
                lambda: self.script_generated.emit(self._generate_select(table_info))
            )
            menu.addAction(select_action)
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            return
        menu = QMenu(self)
        create_action = QAction("Gerar CREATE TABLE", self)
        create_action.triggered.connect(
            lambda: self.script_generated.emit(self._generate_create_table(table_info))
        )
        menu.addAction(create_action)
        drop_action = QAction("Gerar DROP TABLE", self)
        drop_action.triggered.connect(
            lambda: self.script_generated.emit(self._generate_drop_table(table_info))
        )
        menu.addAction(drop_action)
        select_action = QAction("Gerar SELECT *", self)
        select_action.triggered.connect(
            lambda: self.script_generated.emit(self._generate_select(table_info))
        )
        menu.addAction(select_action)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int):
        data = item.data(0, Qt.UserRole)
        if data and data != "__group__":
            self.item_insert_requested.emit(data)

    def focus_filter(self):
        self._tree.setFocus()
