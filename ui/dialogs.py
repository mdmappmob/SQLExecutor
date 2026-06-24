from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


def show_critical(parent, title: str, message: str):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumSize(520, 200)
    dialog.setModal(True)

    layout = QVBoxLayout(dialog)

    text = QTextEdit()
    text.setPlainText(message)
    text.setReadOnly(True)
    text.setStyleSheet("""
        QTextEdit {
            background-color: #1e1e1e; color: #f8f8f8;
            font-family: Consolas, monospace; font-size: 12px;
            border: 1px solid #555; padding: 8px;
        }
    """)
    layout.addWidget(text)

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    close_btn = QPushButton("Fechar")
    close_btn.setStyleSheet("""
        QPushButton { padding: 6px 24px; font-weight: bold; }
    """)
    close_btn.clicked.connect(dialog.accept)
    btn_layout.addWidget(close_btn)
    layout.addLayout(btn_layout)

    dialog.exec()
