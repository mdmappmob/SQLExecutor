from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMessageBox, QApplication,
    QDialog, QLabel, QPushButton, QFileDialog, QMenuBar,
    QDockWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QAction

import re

from application.use_cases import ConnectionUseCase, SQLExecutionUseCase
from infrastructure.adapters.adapter_factory import AdapterFactory
from infrastructure.logger import CSVLogger
from infrastructure.config_manager import ConfigManager
from ui.sql_editor import SQLEditor
from ui.result_panel import ResultPanel
from ui.connection_dialog import ConnectionDialog
from ui.import_dialog import ImportDialog
from ui.parameter_dialog import ParameterDialog
from ui.schema_browser import SchemaBrowser
from ui.history_panel import HistoryPanel
from ui.bookmarks_panel import BookmarksPanel
from infrastructure.i18n import I18N
from infrastructure.session import save_session, load_session
from infrastructure.version import __version__


def _strip_comments(sql: str) -> str:
    result = []
    i = 0
    n = len(sql)
    while i < n:
        if sql[i:i+2] == '/*':
            end = sql.find('*/', i+2)
            if end == -1:
                break
            i = end + 2
            continue
        if sql[i:i+2] == '--':
            end = sql.find('\n', i+2)
            if end == -1:
                break
            i = end + 1
            continue
        result.append(sql[i])
        i += 1
    return ''.join(result)


def _is_single_table_select(sql: str) -> tuple[bool, str]:
    cleaned = _strip_comments(sql).strip()
    upper = cleaned.upper()

    if not upper.startswith("SELECT"):
        return False, ""

    for kw in ("JOIN", "UNION", "INTERSECT", "EXCEPT", "APPLY"):
        if re.search(r'\b' + kw + r'\b', upper):
            return False, ""

    m = re.search(r'\bFROM\b', upper)
    if not m:
        return False, ""

    after_from = cleaned[m.end():].strip()
    m2 = re.match(r'(?:\[([^\]]+)\]|([a-zA-Z_]\w*))(?:\s*\.\s*(?:\[([^\]]+)\]|([a-zA-Z_]\w*)))?', after_from)
    if not m2:
        return False, ""

    schema = m2.group(1) or m2.group(2) or ""
    table = m2.group(3) or m2.group(4) or ""
    if table:
        name = f"[{schema}].[{table}]" if schema else f"[{table}]"
    else:
        name = f"[{schema}]" if schema else ""
    return bool(name), name


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{I18N.main_window['title']} v{__version__}")
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        self._db_type = "mssql"
        self._logger = CSVLogger()
        self._config_mgr = ConfigManager()
        self._adapter = AdapterFactory.create(self._db_type)
        self._connection_uc = ConnectionUseCase(self._adapter, self._logger, self._db_type)
        self._execution_uc = SQLExecutionUseCase(self._adapter, self._logger)
        self._last_parameter_values: dict[str, str] = {}

        self._build_ui()
        self._build_menu_bar()
        self._connect_signals()
        self._setup_shortcuts()
        self._auto_connect()
        self._restore_session()

    def _show_error(self, title: str, message: str):
        QMessageBox.critical(self, title, message)

    def _build_menu_bar(self):
        menubar = self.menuBar()

        conn_menu = menubar.addMenu("&Conexão")
        self._connect_action = QAction("&Conectar...", self)
        self._connect_action.triggered.connect(self._on_connect_dialog)
        conn_menu.addAction(self._connect_action)

        self._disconnect_action = QAction("&Desconectar", self)
        self._disconnect_action.setEnabled(False)
        self._disconnect_action.triggered.connect(self._on_disconnect)
        conn_menu.addAction(self._disconnect_action)

        self._file_menu = menubar.addMenu("&Arquivo")
        self._file_menu.setEnabled(False)
        open_action = QAction("&Abrir SQL...", self)
        open_action.triggered.connect(self._on_open_file)
        self._file_menu.addAction(open_action)

        save_action = QAction("&Salvar", self)
        save_action.triggered.connect(self.sql_editor._save_current_tab)
        self._file_menu.addAction(save_action)

        save_as_action = QAction("Salvar &como...", self)
        save_as_action.triggered.connect(self.sql_editor._save_as_current_tab)
        self._file_menu.addAction(save_as_action)

        conn_menu.addSeparator()
        exit_action = QAction("&Sair", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        conn_menu.addAction(exit_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 2, 6, 6)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0; height: 5px;
            }
            QSplitter::handle:hover {
                background-color: #b0b0b0;
            }
        """)
        self.sql_editor = SQLEditor()
        self.result_panel = ResultPanel()
        self.result_panel.set_adapter(self._adapter)
        splitter.addWidget(self.sql_editor)
        splitter.addWidget(self.result_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        self.sql_editor.add_left_button(self.result_panel.save_btn)
        self.sql_editor.add_left_button(self.result_panel.export_btn)

        self._schema_browser = SchemaBrowser()
        self._schema_browser.item_insert_requested.connect(self._on_schema_insert)
        self._schema_dock = QDockWidget("Navegador", self)
        self._schema_dock.setWidget(self._schema_browser)
        self._schema_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self._schema_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._schema_dock.setMinimumWidth(200)
        self._schema_dock.setMaximumWidth(350)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._schema_dock)

        self._history_panel = HistoryPanel()
        self._history_panel.load_query_requested.connect(self._on_history_load)
        self._history_dock = QDockWidget("Histórico", self)
        self._history_dock.setWidget(self._history_panel)
        self._history_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self._history_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self._history_dock.setMinimumWidth(200)
        self._history_dock.setMaximumWidth(500)
        self.addDockWidget(Qt.RightDockWidgetArea, self._history_dock)

        self._bookmarks_panel = BookmarksPanel()
        self._bookmarks_panel.load_query_requested.connect(self._on_history_load)
        self._bookmarks_dock = QDockWidget("Favoritos", self)
        self._bookmarks_dock.setWidget(self._bookmarks_panel)
        self._bookmarks_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self._bookmarks_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self._bookmarks_dock.setMinimumWidth(180)
        self._bookmarks_dock.setMaximumWidth(350)
        self.addDockWidget(Qt.RightDockWidgetArea, self._bookmarks_dock)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_bar.addPermanentWidget(
            QLabel(f"<span style='color:#555;'>&copy; Márcio Donizeti Marcondes | v{__version__}</span>")
        )

        self._conn_status_widget = QWidget()
        conn_status_layout = QHBoxLayout(self._conn_status_widget)
        conn_status_layout.setContentsMargins(0, 0, 0, 0)
        conn_status_layout.setSpacing(4)

        self._conn_label = QLabel(I18N.connection_panel["status_disconnected"])
        self._conn_label.setStyleSheet("color: #888; font-weight: bold;")
        conn_status_layout.addWidget(self._conn_label)

        self._disconnect_btn = QPushButton("X")
        self._disconnect_btn.setFixedSize(20, 20)
        self._disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f; color: white; border-radius: 3px;
                font-weight: bold; font-size: 9px; padding: 0;
            }
            QPushButton:hover { background-color: #b71c1c; }
        """)
        self._disconnect_btn.setVisible(False)
        self._disconnect_btn.setToolTip(I18N.connection_panel["disconnect_btn"])
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        conn_status_layout.addWidget(self._disconnect_btn)

        self.status_bar.addPermanentWidget(self._conn_status_widget)
        self.status_bar.showMessage(I18N.main_window["status_ready"])

    def _connect_signals(self):
        self.sql_editor.execute_clicked.connect(self._on_execute)
        self.sql_editor.import_csv_clicked.connect(self._on_import_csv)
        self.result_panel.status_message.connect(self.status_bar.showMessage)

    def _setup_shortcuts(self):
        sc = QShortcut(QKeySequence("F9"), self)
        sc.activated.connect(self._on_execute)
        sc = QShortcut(QKeySequence("Ctrl+Return"), self)
        sc.activated.connect(self._on_execute)
        sc = QShortcut(QKeySequence("Escape"), self)
        sc.activated.connect(self._on_cancel)
        sc = QShortcut(QKeySequence("Ctrl+F"), self)
        sc.activated.connect(self.sql_editor.show_find)
        sc = QShortcut(QKeySequence("Ctrl+H"), self)
        sc.activated.connect(self.sql_editor.show_replace)
        sc = QShortcut(QKeySequence("F3"), self)
        sc.activated.connect(self.sql_editor.find_next)
        sc = QShortcut(QKeySequence("Shift+F3"), self)
        sc.activated.connect(self.sql_editor.find_previous)

        for key, callback in [
            ("Ctrl+O", self._on_open_file),
            ("Ctrl+S", self.sql_editor._save_current_tab),
            ("Ctrl+Shift+S", self.sql_editor._save_as_current_tab),
            ("Ctrl+Shift+C", self._on_connect_dialog),
        ]:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(callback)

    def _update_connection_status(self):
        if self._adapter.is_connected():
            srv = self._connection_uc.session.server
            db = self._connection_uc.session.database
            self._conn_label.setText(
                f"[{self._db_type.upper()}] "
                + I18N.connection_panel["status_connected"].format(server=f"{srv}\\{db}")
            )
            self._conn_label.setStyleSheet("color: #107c10; font-weight: bold;")
            self._disconnect_btn.setVisible(True)
            self._connect_action.setEnabled(False)
            self._disconnect_action.setEnabled(True)
            self._file_menu.setEnabled(True)
            self._schema_browser.set_adapter(self._adapter)
        else:
            self._conn_label.setText(I18N.connection_panel["status_disconnected"])
            self._conn_label.setStyleSheet("color: #888; font-weight: bold;")
            self._disconnect_btn.setVisible(False)
            self._connect_action.setEnabled(True)
            self._disconnect_action.setEnabled(False)
            self._file_menu.setEnabled(False)
            self._schema_browser.set_adapter(None)

    def _load_config(self) -> dict:
        return self._config_mgr.load()

    def _auto_connect(self):
        if not self._config_mgr.has_config():
            return
        cfg = self._config_mgr.load()
        db_type = cfg.get("db_type", "mssql")
        if db_type != self._db_type:
            self._db_type = db_type
            self._adapter = AdapterFactory.create(self._db_type)
            self._connection_uc = ConnectionUseCase(self._adapter, self._logger, self._db_type)
            self._execution_uc = SQLExecutionUseCase(self._adapter, self._logger)
        self.status_bar.showMessage(I18N.main_window["auto_connecting"].format(server=cfg['server']))
        QApplication.processEvents()
        self._connection_uc.connect(
            server=cfg["server"],
            database=cfg["database"],
            username=cfg["username"],
            password=cfg.get("password", ""),
            use_windows_auth=cfg["use_windows_auth"],
            timeout=cfg["timeout"],
        )
        session = self._connection_uc.session
        if session.status.value == "Connected":
            self.sql_editor.set_connected(True)
            self.sql_editor.focus_sql()
            self._update_connection_status()
            self.status_bar.showMessage(
                I18N.main_window["auto_connected"].format(server=cfg['server'], db=cfg['database'])
            )
        else:
            self._update_connection_status()
            self.status_bar.showMessage(I18N.main_window["auto_connect_fail"], 5000)

    def _on_connect_dialog(self):
        try:
            config = self._load_config()
            dialog = ConnectionDialog(self, config)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao abrir diálogo de conexão:\n{e}")
            return
        if dialog.exec() != QDialog.Accepted:
            return

        config = dialog.get_config()
        db_type = config["db_type"]
        if not config["database"] or (db_type == "mssql" and not config["server"]):
            QMessageBox.warning(self, I18N.main_window["validation_title"],
                                I18N.main_window["required_server_db"])
            return

        if config["db_type"] != self._db_type:
            self._db_type = config["db_type"]
            self._adapter = AdapterFactory.create(self._db_type)
            self._connection_uc = ConnectionUseCase(self._adapter, self._logger, self._db_type)
            self._execution_uc = SQLExecutionUseCase(self._adapter, self._logger)

        self.status_bar.showMessage(I18N.main_window["connecting"])
        QApplication.processEvents()

        session = self._connection_uc.connect(
            server=config["server"],
            database=config["database"],
            username=config["username"],
            password=config["password"],
            use_windows_auth=config["use_windows_auth"],
            timeout=config["timeout"],
        )

        if session.status.value == "Connected":
            self.sql_editor.set_connected(True)
            self.sql_editor.focus_sql()
            self._update_connection_status()
            self.status_bar.showMessage(
                I18N.main_window["connected_to"].format(server=config['server'], db=config['database'])
            )
            self._config_mgr.save(config)
        else:
            self._update_connection_status()
            self.status_bar.showMessage(I18N.main_window["connection_failed"])

    def _on_disconnect(self):
        self._connection_uc.disconnect()
        self.sql_editor.set_connected(False)
        self.sql_editor.clear_status()
        self.result_panel.clear()
        self._update_connection_status()
        self._connect_action.setEnabled(True)
        self.status_bar.showMessage(I18N.main_window["disconnected"])

    def _on_open_file(self):
        if not self._adapter.is_connected():
            self.status_bar.showMessage("Conecte-se a um banco primeiro", 3000)
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Abrir SQL", "", "Arquivos SQL (*.sql);;Todos (*)"
        )
        if file_path:
            self._open_sql_file(file_path)

    def open_sql_file(self, file_path: str):
        self._open_sql_file(file_path)

    def _open_sql_file(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.sql_editor._add_tab(content)
            info = self.sql_editor._current_tab()
            info["file_path"] = file_path
            self.sql_editor.tab_widget.setTabText(
                self.sql_editor.tab_widget.currentIndex(),
                file_path.split("\\")[-1]
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Abrir", str(e))

    def _extract_param_info(self, sql: str) -> list[tuple[str, str]]:
        matches = re.finditer(r'(?<!:):([a-zA-Z_]\w*)', sql)
        seen: set[str] = set()
        result: list[tuple[str, str]] = []
        for m in matches:
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            pos = m.start()
            before = sql[pos - 1] if pos > 0 else ""
            if before == "'":
                result.append((name, "texto"))
            elif before in ("=", " ", "(", ",", ">", "<", "!"):
                result.append((name, "número"))
            else:
                result.append((name, "auto"))
        return result

    def _extract_parameters(self, sql: str) -> list[str]:
        return [p[0] for p in self._extract_param_info(sql)]

    @staticmethod
    def _normalize_date(val: str) -> str:
        m = re.match(r'^(\d{2})/(\d{2})/(\d{2,4})$', val.strip())
        if m:
            d, mo, y = m.groups()
            y4 = y if len(y) == 4 else "20" + y
            return f"{y4}{mo}{d}"
        m = re.match(r'^(\d{2})/(\d{2})/(\d{2,4})\s+(\d{2}:\d{2}(?::\d{2})?)$', val.strip())
        if m:
            d, mo, y, t = m.groups()
            y4 = y if len(y) == 4 else "20" + y
            return f"{y4}{mo}{d} {t}"
        return val

    def _quote_sql(self, val: str) -> str:
        return "'" + val.replace("'", "''") + "'"

    @staticmethod
    def _is_sql_number(val: str) -> bool:
        try:
            float(val.replace(",", "."))
            return True
        except ValueError:
            return False

    def _inject_parameters(self, sql: str, values: dict[str, str]) -> str:
        for name in sorted(values.keys(), key=len, reverse=True):
            val = values[name].strip()
            info = self._extract_param_info(sql)
            param_types = {n: t for n, t in info}
            ptype = param_types.get(name, "auto")

            if ptype == "texto":
                sql = re.sub(rf"':{re.escape(name)}(?!\w)'", lambda m: self._quote_sql(self._normalize_date(val)), sql)
            elif ptype == "número" and self._is_sql_number(val):
                sql = re.sub(rf'(?<!:):{re.escape(name)}(?!\w)', val.replace(",", "."), sql)
            else:
                sql = re.sub(rf'(?<!:):{re.escape(name)}(?!\w)', self._quote_sql(self._normalize_date(val)), sql)
        return sql

    def _strip_param_lines(self, sql: str) -> str:
        lines = sql.split('\n')
        clean = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if re.match(r'^:[a-zA-Z_]\w*$', s):
                continue
            while re.match(r'^:[a-zA-Z_]\w*\s', s):
                s = re.sub(r'^:[a-zA-Z_]\w*\s*', '', s).strip()
            clean.append(s)
        return '\n'.join(clean).strip()

    def _on_execute(self):
        sql_text = self.sql_editor.get_sql()
        if not sql_text:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.main_window["no_sql"])
            return

        if not self._adapter.is_connected():
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.main_window["not_connected"])
            return

        clean_base = self._strip_param_lines(sql_text)
        if not clean_base:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.main_window["no_sql"])
            return

        params = self._extract_parameters(sql_text)
        if params:
            dialog = ParameterDialog(params, self, self._last_parameter_values)
            if dialog.exec() != QDialog.Accepted:
                return
            self._last_parameter_values = dialog.get_values()
            sql_to_execute = self._inject_parameters(clean_base, self._last_parameter_values)
        else:
            sql_to_execute = clean_base

        sql_upper = sql_to_execute.strip().upper()
        is_delete = sql_upper.startswith("DELETE")
        is_update = sql_upper.startswith("UPDATE")

        if (is_delete or is_update) and "WHERE" not in sql_upper:
            reply = QMessageBox.warning(
                self, I18N.main_window["confirm_title"],
                I18N.main_window["confirm_nowhere"].format(cmd=sql_upper.split()[0]),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        try:
            self.status_bar.showMessage(I18N.main_window["executing"])
            self.sql_editor.execute_btn.setEnabled(False)
            self.sql_editor.execute_btn.setText(I18N.main_window["executing"])
            QApplication.processEvents()

            self.sql_editor.add_to_history(sql_text)

            result = self._execution_uc.execute(sql_to_execute)

            if result.success:
                if result.columns:
                    is_editable, table_name = _is_single_table_select(sql_text)
                    self.result_panel.show_results(
                        result.columns, result.rows, result.message,
                        editable=is_editable, table_name=table_name
                    )
                    self.sql_editor.set_rows_returned(result.rows_affected)
                else:
                    self.result_panel.show_message(result.message)
                    self.sql_editor.set_rows_affected(result.rows_affected)
                self.status_bar.showMessage(result.message, 10000)
            else:
                self.result_panel.show_error(result.message)
                self.status_bar.showMessage(I18N.main_window["execution_failed"])
        except ValueError as e:
            self.result_panel.show_error(str(e))
            self.status_bar.showMessage(I18N.main_window["validation_error"])
        except Exception as e:
            self.result_panel.show_error(I18N.main_window["unexpected_error"] + f": {e}")
            self.status_bar.showMessage(I18N.main_window["unexpected_error"])
        finally:
            self.sql_editor.execute_btn.setEnabled(True)
            self.sql_editor.execute_btn.setText(I18N.main_window["execute"])
            self._history_panel.refresh()

    def _on_import_csv(self):
        dialog = ImportDialog(self._adapter, self)
        if dialog.exec():
            self.status_bar.showMessage(I18N.main_window["csv_import_ok"], 10000)
        else:
            self.status_bar.showMessage(I18N.main_window["csv_import_cancel"])

    def _on_cancel(self):
        if self.sql_editor.is_search_visible():
            self.sql_editor.hide_search()
            self.sql_editor.focus_sql()
            return
        self.result_panel.clear()
        self.sql_editor.clear_status()
        self.status_bar.showMessage(I18N.main_window["cancelled"])

    def _on_schema_insert(self, name: str):
        editor = self.sql_editor._current_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.insertText(name)
            editor.setTextCursor(cursor)
            editor.setFocus()

    def _on_history_load(self, sql: str):
        editor = self.sql_editor._current_editor()
        if editor:
            editor.setPlainText(sql)
            editor.setFocus()

    def _save_session(self):
        tabs_data = []
        for i in range(self.sql_editor.tab_widget.count()):
            tab = self.sql_editor._tabs[i] if i < len(self.sql_editor._tabs) else {}
            editor = tab.get("editor")
            content = editor.toPlainText() if editor else ""
            file_path = tab.get("file_path", "")
            tab_name = tab.get("tab_name", "")
            tabs_data.append({
                "name": tab_name,
                "file_path": file_path,
                "content": content,
            })
        save_session({"tabs": tabs_data})

    def _restore_session(self):
        data = load_session()
        tabs = data.get("tabs", [])
        for t in tabs:
            content = t.get("content", "")
            file_path = t.get("file_path", "")
            name = t.get("name", "")
            self.sql_editor._add_tab(content)
            if file_path:
                self.sql_editor._tabs[-1]["file_path"] = file_path
            if name:
                self.sql_editor._tabs[-1]["tab_name"] = name
                idx = self.sql_editor.tab_widget.count() - 1
                self.sql_editor.tab_widget.setTabText(idx, name)

    def closeEvent(self, event):
        self._save_session()
        self._on_disconnect()
        super().closeEvent(event)
