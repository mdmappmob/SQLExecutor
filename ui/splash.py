from PySide6.QtWidgets import QSplashScreen
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, QPen, QBrush, QPolygon

from infrastructure.version import __version__


def _generate_splash_pixmap() -> QPixmap:
    pm = QPixmap(500, 300)
    pm.fill(QColor("#2b2b2b"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    p.setPen(QPen(QColor("#107c10"), 4))
    p.setBrush(QBrush(QColor("#107c10")))
    cx, cy = 80, 100
    poly = QPolygon([
        QPoint(cx + 40, cy),
        QPoint(cx - 20, cy - 30),
        QPoint(cx - 20, cy + 30),
    ])
    p.drawPolygon(poly)

    p.setPen(QColor("#ffffff"))
    f = QFont("Segoe UI", 26, QFont.Bold)
    p.setFont(f)
    p.drawText(140, 80, "SQL Executor")

    f2 = QFont("Segoe UI", 14)
    p.setFont(f2)
    p.setPen(QColor("#aaaaaa"))
    p.drawText(140, 115, f"Versão {__version__}")

    f3 = QFont("Segoe UI", 10)
    p.setFont(f3)
    p.setPen(QColor("#888888"))
    p.drawText(140, 145, "Carregando...")

    p.setPen(QColor("#555555"))
    f4 = QFont("Segoe UI", 8)
    p.setFont(f4)
    p.drawText(QRect(0, 220, 500, 30), Qt.AlignCenter, "Márcio Donizeti Marcondes")
    p.drawText(QRect(0, 255, 500, 30), Qt.AlignCenter, "DevTools")

    p.end()
    return pm


def create_splash() -> QSplashScreen:
    pm = _generate_splash_pixmap()
    splash = QSplashScreen(pm)
    splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    return splash
