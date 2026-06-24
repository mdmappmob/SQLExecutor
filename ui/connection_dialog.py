from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QLabel, QSpinBox, QComboBox, QMessageBox, QApplication,
    QWidget, QTextEdit
)
from PySide6.QtCore import Qt

from infrastructure.i18n import I18N
from infrastructure.adapters.db_types import DBType


class ConnectionDialog(QDialog):
    def __init__(self, parent=None, config: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Conexão com Banco de Dados")
        self.setMinimumWidth(480)
        self._loading = False
        self._build_ui()
        if config:
            self._load_config(config)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.db_type_combo = QComboBox()
        for value, label in DBType.choices():
            self.db_type_combo.addItem(label, value)
        self.db_type_combo.currentIndexChanged.connect(self._on_db_type_changed)
        form.addRow("Tipo de Banco:", self.db_type_combo)

        self._server_label = QLabel(I18N.connection_panel["server_label"])
        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText(I18N.connection_panel["server_ph"])
        self._server_row = QWidget()
        row_layout = QHBoxLayout(self._server_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.server_edit)
        form.addRow(self._server_label, self._server_row)

        self._database_label = QLabel(I18N.connection_panel["database_label"])
        self.database_edit = QLineEdit()
        self.database_edit.setPlaceholderText(I18N.connection_panel["database_ph"])
        form.addRow(self._database_label, self.database_edit)

        self._auth_container = QWidget()
        auth_form = QFormLayout(self._auth_container)
        auth_form.setContentsMargins(0, 0, 0, 0)
        auth_form.setSpacing(8)

        auth_choice_layout = QHBoxLayout()
        self.auth_group = QButtonGroup(self)
        self.windows_auth_rb = QRadioButton(I18N.connection_panel["windows_auth"])
        self.sql_auth_rb = QRadioButton(I18N.connection_panel["sql_auth"])
        self.windows_auth_rb.setChecked(True)
        self.auth_group.addButton(self.windows_auth_rb)
        self.auth_group.addButton(self.sql_auth_rb)
        auth_choice_layout.addWidget(self.windows_auth_rb)
        auth_choice_layout.addWidget(self.sql_auth_rb)
        auth_choice_layout.addStretch()
        self._auth_choice_row = QWidget()
        self._auth_choice_row.setLayout(auth_choice_layout)
        auth_form.addRow(I18N.connection_panel["auth_label"], self._auth_choice_row)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText(I18N.connection_panel["username_ph"])
        self.username_edit.setEnabled(False)
        auth_form.addRow(I18N.connection_panel["username_label"], self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText(I18N.connection_panel["password_ph"])
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setEnabled(False)
        auth_form.addRow(I18N.connection_panel["password_label"], self.password_edit)

        self.sql_auth_rb.toggled.connect(lambda checked: (
            self.username_edit.setEnabled(checked),
            self.password_edit.setEnabled(checked)
        ))

        self._auth_label = QLabel(I18N.connection_panel["auth_label"])
        self._auth_label.setVisible(False)
        form.addRow(self._auth_label, self._auth_container)

        timeout_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(I18N.connection_panel["timeout_suffix"])
        timeout_layout.addWidget(self.timeout_spin)
        timeout_layout.addStretch()
        form.addRow(I18N.connection_panel["timeout_label"], timeout_layout)

        layout.addLayout(form)
        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton(I18N.connection_panel["test_btn"])
        self.test_btn.setStyleSheet("""
            QPushButton { background-color: #ff8c00; color: white; padding: 6px 16px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #e67e00; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.test_btn.clicked.connect(self._on_test)

        self.connect_btn = QPushButton(I18N.connection_panel["connect_btn"])
        self.connect_btn.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; padding: 6px 20px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.connect_btn.clicked.connect(self._on_connect)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: #888; color: white; padding: 6px 20px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #666; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMinimumHeight(40)
        self.error_text.setMaximumHeight(120)
        self.error_text.setStyleSheet("""
            QTextEdit {
                color: #d32f2f; font-weight: bold; font-family: Consolas, monospace;
                font-size: 11px; border: 1px solid #d32f2f; padding: 6px;
                background-color: #2d1b1b;
            }
        """)
        self.error_text.setVisible(False)
        layout.addWidget(self.error_text)

        self._update_ui_for_db_type()

    def _load_config(self, config: dict):
        self._loading = True
        db_type = config.get("db_type", "mssql")
        idx = self.db_type_combo.findData(db_type)
        if idx >= 0:
            self.db_type_combo.setCurrentIndex(idx)

        server = config.get("server", "")
        database = config.get("database", "")
        if db_type == "oracle" and server and database and server != database:
            database = f"{server}/{database}"
        elif db_type == "firebird" and server and database and server != database:
            database = f"{server}:{database}"
        elif db_type in ("mysql", "mariadb", "postgresql") and server and database and server != database:
            server = database

        self.server_edit.setText(server if db_type == "mssql" else "")
        self.database_edit.setText(database)
        self.username_edit.setText(config.get("username", ""))
        self.password_edit.setText(config.get("password", ""))
        if not config.get("use_windows_auth", True):
            self.sql_auth_rb.setChecked(True)
        self.timeout_spin.setValue(config.get("timeout", 30))
        self._update_ui_for_db_type()
        self._loading = False

    def _on_db_type_changed(self):
        if self._loading:
            return
        self.server_edit.clear()
        self.database_edit.clear()
        self.username_edit.clear()
        self.password_edit.clear()
        self.windows_auth_rb.setChecked(True)
        self.timeout_spin.setValue(30)
        self.error_text.setVisible(False)
        self._update_ui_for_db_type()

    def _update_ui_for_db_type(self):
        db_type = self.db_type_combo.currentData()
        if db_type == "mssql":
            self._server_label.setVisible(True)
            self._server_row.setVisible(True)
            self._database_label.setText(I18N.connection_panel["database_label"])
            self.database_edit.setPlaceholderText(I18N.connection_panel["database_ph"])
            self._auth_choice_row.setVisible(True)
            self.windows_auth_rb.setChecked(True)
            self.username_edit.setEnabled(False)
            self.password_edit.setEnabled(False)
        elif db_type == "oracle":
            self._server_label.setVisible(False)
            self._server_row.setVisible(False)
            self._database_label.setText("Database / SID")
            self.database_edit.setPlaceholderText("Ex: localhost:1521/XEPDB1 ou TNS_NAME")
            self._auth_choice_row.setVisible(False)
            self.sql_auth_rb.setChecked(True)
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)
        elif db_type == "firebird":
            self._server_label.setVisible(False)
            self._server_row.setVisible(False)
            self._database_label.setText("Database / Caminho")
            self.database_edit.setPlaceholderText("Ex: localhost/3050:C:\\db\\banco.fdb")
            self._auth_choice_row.setVisible(False)
            self.sql_auth_rb.setChecked(True)
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)
        elif db_type in ("mysql", "mariadb"):
            self._server_label.setVisible(True)
            self._server_row.setVisible(True)
            self._database_label.setText("Database / Schema")
            self.database_edit.setPlaceholderText("Ex: meubanco")
            self._auth_choice_row.setVisible(False)
            self.sql_auth_rb.setChecked(True)
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)
        else:  # postgresql
            self._server_label.setVisible(True)
            self._server_row.setVisible(True)
            self._database_label.setText("Database / Schema")
            self.database_edit.setPlaceholderText("Ex: meubanco")
            self._auth_choice_row.setVisible(False)
            self.sql_auth_rb.setChecked(True)
            self.username_edit.setEnabled(True)
            self.password_edit.setEnabled(True)

    def get_config(self) -> dict:
        db_type = self.db_type_combo.currentData()
        use_windows_auth = self.windows_auth_rb.isChecked() if db_type == "mssql" else False
        return {
            "db_type": db_type,
            "server": self.server_edit.text().strip(),
            "database": self.database_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "use_windows_auth": use_windows_auth,
            "timeout": self.timeout_spin.value(),
        }

    def _is_valid(self) -> bool:
        db_type = self.db_type_combo.currentData()
        if not self.database_edit.text().strip():
            return False
        if db_type == "mssql" and not self.server_edit.text().strip():
            return False
        return True

    def _get_connection_use_case(self):
        from application.use_cases import ConnectionUseCase
        from infrastructure.adapters.adapter_factory import AdapterFactory
        from infrastructure.logger import CSVLogger
        db_type = self.db_type_combo.currentData()
        adapter = AdapterFactory.create(db_type)
        logger = CSVLogger()
        return ConnectionUseCase(adapter, logger, db_type)

    def _on_test(self):
        config = self.get_config()
        if not self._is_valid():
            QMessageBox.warning(self, I18N.main_window["validation_title"],
                                "Preencha os campos obrigatórios (Database para Oracle/Firebird; Servidor e Database para MSSQL)")
            return

        self.test_btn.setEnabled(False)
        self.test_btn.setText(I18N.main_window["testing"])
        QApplication.processEvents()

        uc = self._get_connection_use_case()
        success = uc.test_connection(
            server=config["server"],
            database=config["database"],
            username=config["username"],
            password=config["password"],
            use_windows_auth=config["use_windows_auth"],
        )

        self.test_btn.setEnabled(True)
        self.test_btn.setText(I18N.connection_panel["test_btn"])

        if success:
            QMessageBox.information(self, I18N.main_window["test_title"],
                                    I18N.main_window["test_ok"])
            self.error_text.setVisible(False)
        else:
            self.error_text.setPlainText(I18N.main_window["test_fail_msg"])
            self.error_text.setVisible(True)

    def _on_connect(self):
        config = self.get_config()
        if not self._is_valid():
            QMessageBox.warning(self, I18N.main_window["validation_title"],
                                "Preencha os campos obrigatórios (Database para Oracle/Firebird; Servidor e Database para MSSQL)")
            return

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(I18N.main_window["connecting"])
        QApplication.processEvents()

        uc = self._get_connection_use_case()
        session = uc.connect(
            server=config["server"],
            database=config["database"],
            username=config["username"],
            password=config["password"],
            use_windows_auth=config["use_windows_auth"],
            timeout=config["timeout"],
        )

        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(I18N.connection_panel["connect_btn"])

        if session.status.value == "Connected":
            self._config = config
            self.accept()
        else:
            self.error_text.setPlainText(session.error_message)
            self.error_text.setVisible(True)
