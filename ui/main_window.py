from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMessageBox, QApplication, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence

import re

from application.use_cases import ConnectionUseCase, SQLExecutionUseCase
from infrastructure.mssql_adapter import MSSQLAdapter
from infrastructure.logger import CSVLogger
from infrastructure.config_manager import ConfigManager
from ui.connection_panel import ConnectionPanel
from ui.sql_editor import SQLEditor
from ui.result_panel import ResultPanel
from ui.import_dialog import ImportDialog
from ui.parameter_dialog import ParameterDialog
from infrastructure.i18n import I18N


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
        self.setWindowTitle(I18N.main_window["title"])
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        self._adapter = MSSQLAdapter()
        self._logger = CSVLogger()
        self._config_mgr = ConfigManager()
        self._connection_uc = ConnectionUseCase(self._adapter, self._logger)
        self._execution_uc = SQLExecutionUseCase(self._adapter, self._logger)
        self._last_parameter_values: dict[str, str] = {}

        self._build_ui()
        self._load_config()
        self._connect_signals()
        self._setup_shortcuts()
        self._auto_connect()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(6)

        self.connection_panel = ConnectionPanel()
        main_layout.addWidget(self.connection_panel)

        splitter = QSplitter(Qt.Vertical)
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

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(I18N.main_window["status_ready"])

    def _connect_signals(self):
        self.connection_panel.connect_clicked.connect(self._on_connect)
        self.connection_panel.disconnect_clicked.connect(self._on_disconnect)
        self.connection_panel.test_clicked.connect(self._on_test)
        self.sql_editor.execute_clicked.connect(self._on_execute)
        self.sql_editor.import_csv_clicked.connect(self._on_import_csv)
        self.result_panel.status_message.connect(self.status_bar.showMessage)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F5"), self, self._on_execute)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._on_execute)
        QShortcut(QKeySequence("Escape"), self, self._on_cancel)
        QShortcut(QKeySequence("Ctrl+F"), self, self.sql_editor.show_find)
        QShortcut(QKeySequence("Ctrl+H"), self, self.sql_editor.show_replace)
        QShortcut(QKeySequence("F3"), self, self.sql_editor.find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self.sql_editor.find_previous)

    def _on_test(self):
        config = self.connection_panel.get_config()
        if not config["server"] or not config["database"]:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.main_window["required_server_db"])
            return

        self.connection_panel.test_btn.setEnabled(False)
        self.connection_panel.test_btn.setText(I18N.main_window["testing"])
        QApplication.processEvents()

        success = self._connection_uc.test_connection(
            server=config["server"],
            database=config["database"],
            username=config["username"],
            password=config["password"],
            use_windows_auth=config["use_windows_auth"],
        )

        self.connection_panel.test_btn.setEnabled(True)
        self.connection_panel.test_btn.setText(I18N.main_window["test"])

        if success:
            QMessageBox.information(self, I18N.main_window["test_title"], I18N.main_window["test_ok"])
            self.status_bar.showMessage(I18N.main_window["test_success"])
        else:
            QMessageBox.warning(self, I18N.main_window["test_title"], I18N.main_window["test_fail_msg"])
            self.status_bar.showMessage(I18N.main_window["test_fail"])

    def _load_config(self):
        cfg = self._config_mgr.load()
        self.connection_panel.server_edit.setText(cfg["server"])
        self.connection_panel.database_edit.setText(cfg["database"])
        self.connection_panel.username_edit.setText(cfg["username"])
        self.connection_panel.password_edit.setText(cfg.get("password", ""))
        if not cfg["use_windows_auth"]:
            self.connection_panel.sql_auth_rb.setChecked(True)
        self.connection_panel.timeout_spin.setValue(cfg["timeout"])

    def _auto_connect(self):
        if not self._config_mgr.has_config():
            return
        cfg = self._config_mgr.load()
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
            self.connection_panel.set_connected_state(True)
            self.sql_editor.set_connected(True)
            self.sql_editor.focus_sql()
            self.status_bar.showMessage(I18N.main_window["auto_connected"].format(server=cfg['server'], db=cfg['database']))
        else:
            self.status_bar.showMessage(I18N.main_window["auto_connect_fail"], 5000)

    def _on_connect(self):
        config = self.connection_panel.get_config()
        if not config["server"] or not config["database"]:
            QMessageBox.warning(self, I18N.main_window["validation_title"], I18N.main_window["required_server_db"])
            return

        self.connection_panel.connect_btn.setEnabled(False)
        self.connection_panel.connect_btn.setText(I18N.main_window["connecting"])
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
            self.connection_panel.set_connected_state(True)
            self.sql_editor.set_connected(True)
            self.sql_editor.focus_sql()
            self.status_bar.showMessage(I18N.main_window["connected_to"].format(server=config['server'], db=config['database']))
            self._config_mgr.save(config)
        else:
            self.connection_panel.set_error(session.error_message)
            self.connection_panel.connect_btn.setEnabled(True)
            self.status_bar.showMessage(I18N.main_window["connection_failed"])

        self.connection_panel.connect_btn.setText(I18N.main_window["connect"])

    def _on_disconnect(self):
        self._connection_uc.disconnect()
        self.connection_panel.set_connected_state(False)
        self.sql_editor.set_connected(False)
        self.sql_editor.clear_status()
        self.result_panel.clear()
        self.status_bar.showMessage(I18N.main_window["disconnected"])

    def _extract_parameters(self, sql: str) -> list[str]:
        matches = re.findall(r'(?<!:):([a-zA-Z_]\w*)', sql)
        seen: set[str] = set()
        return [m for m in matches if not (m in seen or seen.add(m))]

    def _inject_parameters(self, sql: str, values: dict[str, str]) -> str:
        for name in sorted(values.keys(), key=len, reverse=True):
            val = values[name]
            sql = re.sub(rf'(?<!:):{re.escape(name)}(?!\w)', lambda m: val, sql)
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
                self.status_bar.showMessage(
                    I18N.main_window["completed_in"].format(ms=result.duration_ms, msg=result.message), 10000
                )
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

    def closeEvent(self, event):
        self._on_disconnect()
        super().closeEvent(event)
