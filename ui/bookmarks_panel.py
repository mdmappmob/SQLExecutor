from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QMenu
)
from PySide6.QtCore import Qt, Signal

from infrastructure.i18n import I18N
from infrastructure.bookmarks import save_bookmarks, load_bookmarks


class BookmarksPanel(QWidget):
    load_query_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bookmarks: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("Favoritos")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

    def refresh(self):
        self._bookmarks = load_bookmarks()
        self._list.clear()
        for bm in self._bookmarks:
            name = bm.get("name", "Sem nome")
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, bm.get("sql", ""))
            item.setToolTip(bm.get("sql", ""))
            self._list.addItem(item)

    def add_bookmark(self, sql: str):
        name, ok = QInputDialog.getText(self, "Salvar Favorito", "Nome do favorito:")
        if not ok or not name.strip():
            return
        self._bookmarks.append({"name": name.strip(), "sql": sql})
        save_bookmarks(self._bookmarks)
        self.refresh()

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction("Carregar", lambda: self._load_item(item))
        menu.addAction("Remover", lambda: self._remove_item(item))
        menu.exec(self._list.mapToGlobal(pos))

    def _on_item_double_clicked(self, item):
        self._load_item(item)

    def _load_item(self, item):
        sql = item.data(Qt.UserRole)
        if sql:
            self.load_query_requested.emit(sql)

    def _remove_item(self, item):
        idx = self._list.row(item)
        if 0 <= idx < len(self._bookmarks):
            reply = QMessageBox.question(
                self, "Remover Favorito",
                f"Remover '{self._bookmarks[idx]['name']}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._bookmarks.pop(idx)
                save_bookmarks(self._bookmarks)
                self.refresh()
