from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from infrastructure.version import __version__, __build__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sobre")
        self.setFixedSize(400, 300)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("SQL Executor")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0078d4;")
        layout.addWidget(title)

        layout.addSpacing(4)

        info_data = [
            ("Versão:", f"v{__version__}"),
            ("Build:", __build__),
            ("Autor:", "Márcio Donizeti Marcondes"),
        ]
        for label, value in info_data:
            row = QLabel(f"<b>{label}</b> {value}")
            row.setAlignment(Qt.AlignCenter)
            row.setStyleSheet("font-size: 13px; color: #333;")
            layout.addWidget(row)

        layout.addSpacing(8)

        tech = QLabel(
            "<b>Tecnologias:</b> Python, PySide6, PyInstaller"
        )
        tech.setAlignment(Qt.AlignCenter)
        tech.setStyleSheet("font-size: 12px; color: #555;")
        tech.setWordWrap(True)
        layout.addWidget(tech)

        dbs = QLabel(
            "<b>Bancos suportados:</b> MSSQL, Oracle, Firebird, PostgreSQL, MySQL/MariaDB, SQLite"
        )
        dbs.setAlignment(Qt.AlignCenter)
        dbs.setStyleSheet("font-size: 12px; color: #555;")
        dbs.setWordWrap(True)
        layout.addWidget(dbs)

        desc = QLabel(
            "Ferramenta multiplataforma para execução e migração de SQL."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 12px; color: #777; font-style: italic;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        close_btn = QPushButton("Fechar")
        close_btn.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; padding: 6px 24px;
                          font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #106ebe; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn, 0, Qt.AlignCenter)
        layout.addLayout(btn_layout)
