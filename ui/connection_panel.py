from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QCheckBox, QPushButton, QRadioButton,
    QButtonGroup, QLabel, QSpinBox, QToolButton, QWidget
)
from PySide6.QtCore import Signal, Qt

from infrastructure.i18n import I18N


class ConnectionPanel(QGroupBox):
    connect_clicked = Signal()
    disconnect_clicked = Signal()
    test_clicked = Signal()
    collapse_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__("", parent)
        self._collapsed = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(9, 4, 9, 9)

        header = QHBoxLayout()
        title_label = QLabel(I18N.connection_panel["group"])
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
        header.addWidget(title_label)
        header.addStretch()

        self._toggle_btn = QToolButton()
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.setArrowType(Qt.DownArrow)
        self._toggle_btn.setToolTip(I18N.connection_panel["collapse"])
        self._toggle_btn.setStyleSheet("QToolButton { border: none; padding: 2px; }")
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        header.addWidget(self._toggle_btn)
        layout.addLayout(header)

        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        form = QFormLayout()

        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText(I18N.connection_panel["server_ph"])
        form.addRow(I18N.connection_panel["server_label"], self.server_edit)

        self.database_edit = QLineEdit()
        self.database_edit.setPlaceholderText(I18N.connection_panel["database_ph"])
        form.addRow(I18N.connection_panel["database_label"], self.database_edit)

        auth_layout = QHBoxLayout()
        self.auth_group = QButtonGroup(self)
        self.windows_auth_rb = QRadioButton(I18N.connection_panel["windows_auth"])
        self.sql_auth_rb = QRadioButton(I18N.connection_panel["sql_auth"])
        self.windows_auth_rb.setChecked(True)
        self.auth_group.addButton(self.windows_auth_rb)
        self.auth_group.addButton(self.sql_auth_rb)
        auth_layout.addWidget(self.windows_auth_rb)
        auth_layout.addWidget(self.sql_auth_rb)
        auth_layout.addStretch()
        form.addRow(I18N.connection_panel["auth_label"], auth_layout)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText(I18N.connection_panel["username_ph"])
        self.username_edit.setEnabled(False)
        form.addRow(I18N.connection_panel["username_label"], self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText(I18N.connection_panel["password_ph"])
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setEnabled(False)
        form.addRow(I18N.connection_panel["password_label"], self.password_edit)

        self.sql_auth_rb.toggled.connect(lambda checked: (
            self.username_edit.setEnabled(checked),
            self.password_edit.setEnabled(checked)
        ))

        timeout_layout = QHBoxLayout()
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(I18N.connection_panel["timeout_suffix"])
        timeout_layout.addWidget(self.timeout_spin)
        timeout_layout.addStretch()
        form.addRow(I18N.connection_panel["timeout_label"], timeout_layout)

        content_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton(I18N.connection_panel["test_btn"])
        self.test_btn.setStyleSheet("""
            QPushButton { background-color: #ff8c00; color: white; padding: 6px 16px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #e67e00; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.connect_btn = QPushButton(I18N.connection_panel["connect_btn"])
        self.connect_btn.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; padding: 6px 20px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #106ebe; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.disconnect_btn = QPushButton(I18N.connection_panel["disconnect_btn"])
        self.disconnect_btn.setEnabled(False)
        self.test_btn.clicked.connect(self.test_clicked.emit)
        self.connect_btn.clicked.connect(self.connect_clicked.emit)
        self.disconnect_btn.clicked.connect(self.disconnect_clicked.emit)

        btn_layout.addWidget(self.test_btn)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.disconnect_btn)
        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)

        layout.addWidget(self._content)

        self.status_label = QLabel(I18N.connection_panel["status_disconnected"])
        self.status_label.setStyleSheet("color: #888; font-weight: bold;")
        layout.addWidget(self.status_label)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        if self._collapsed:
            self._toggle_btn.setArrowType(Qt.UpArrow)
            self._toggle_btn.setToolTip(I18N.connection_panel["expand"])
        else:
            self._toggle_btn.setArrowType(Qt.DownArrow)
            self._toggle_btn.setToolTip(I18N.connection_panel["collapse"])
        self.collapse_changed.emit(self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_connected_state(self, connected: bool):
        self.test_btn.setEnabled(not connected)
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.server_edit.setEnabled(not connected)
        self.database_edit.setEnabled(not connected)
        self.windows_auth_rb.setEnabled(not connected)
        self.sql_auth_rb.setEnabled(not connected)
        self.username_edit.setEnabled(not connected and self.sql_auth_rb.isChecked())
        self.password_edit.setEnabled(not connected and self.sql_auth_rb.isChecked())
        self.timeout_spin.setEnabled(not connected)
        if connected:
            self.status_label.setStyleSheet("color: #107c10; font-weight: bold;")
            self.status_label.setText(
                I18N.connection_panel["status_connected"].format(server=self.server_edit.text())
            )
        else:
            self.status_label.setStyleSheet("color: #888; font-weight: bold;")
            self.status_label.setText(I18N.connection_panel["status_disconnected"])

    def set_error(self, message: str):
        self.status_label.setStyleSheet("color: #d32f2f; font-weight: bold;")
        self.status_label.setText(
            I18N.connection_panel["status_error"].format(msg=message)
        )

    def get_config(self) -> dict:
        return {
            "server": self.server_edit.text().strip(),
            "database": self.database_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "use_windows_auth": self.windows_auth_rb.isChecked(),
            "timeout": self.timeout_spin.value(),
        }
