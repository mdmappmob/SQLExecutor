import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon, QFont
from ui.main_window import MainWindow
from ui.splash import create_splash


def _make_app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(QColor("#2b2b2b"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    cx, cy = 128, 115
    size = 90
    p.setPen(QPen(QColor("#107c10"), 6))
    p.setBrush(QBrush(QColor("#107c10")))
    poly = QPolygon([
        QPoint(cx + size, cy),
        QPoint(cx - size // 2, cy - int(size * 0.75)),
        QPoint(cx - size // 2, cy + int(size * 0.75)),
    ])
    p.drawPolygon(poly)
    p.setPen(QColor("#ffffff"))
    f = QFont("Segoe UI", 22, QFont.Bold)
    p.setFont(f)
    p.drawText(QRect(0, 200, 256, 40), Qt.AlignCenter, "SQL")
    p.end()
    return QIcon(pm)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("SQL Executor")
    app.setOrganizationName("DevTools")

    app.setWindowIcon(_make_app_icon())

    splash = create_splash()
    splash.show()
    splash.raise_()
    app.processEvents()

    window = MainWindow()
    window.show()
    splash.finish(window)

    for arg in sys.argv[1:]:
        if os.path.isfile(arg) and arg.lower().endswith('.sql'):
            window.open_sql_file(arg)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
