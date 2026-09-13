"""Drawn app icon + the animated Pac-Man companion, both via QPainter.

No external image assets -- everything here is vector shapes so it stays
crisp at any size and matches the rest of the UI's palette exactly.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

BG_TOP = QColor("#6C4FE0")
BG_BOTTOM = QColor("#4630A8")
ACCENT_YELLOW = QColor("#FFD23F")
INK_WHITE = QColor("#F5F3FF")


def draw_app_icon(size: int = 256) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = size * 0.06
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = size * 0.22

    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0, BG_TOP)
    gradient.setColorAt(1, BG_BOTTOM)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, gradient)

    # Notepad glyph: a white card with three lines
    pad_rect = QRectF(size * 0.30, size * 0.24, size * 0.40, size * 0.50)
    painter.setPen(Qt.NoPen)
    painter.setBrush(INK_WHITE)
    painter.drawRoundedRect(pad_rect, size * 0.03, size * 0.03)
    pen = QPen(BG_BOTTOM, size * 0.02)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    for i in range(3):
        y = pad_rect.top() + pad_rect.height() * (0.32 + i * 0.2)
        painter.drawLine(
            int(pad_rect.left() + pad_rect.width() * 0.18), int(y),
            int(pad_rect.right() - pad_rect.width() * 0.18), int(y),
        )

    # Pac-Man companion peeking from the bottom-right corner
    pac_r = size * 0.22
    pac_center = (rect.right() - pac_r * 0.55, rect.bottom() - pac_r * 0.55)
    pac_rect = QRectF(pac_center[0] - pac_r, pac_center[1] - pac_r, pac_r * 2, pac_r * 2)
    painter.setBrush(ACCENT_YELLOW)
    painter.setPen(Qt.NoPen)
    painter.drawPie(pac_rect, 30 * 16, 300 * 16)

    painter.end()
    return pixmap


def app_icon() -> QIcon:
    return QIcon(draw_app_icon())


if __name__ == "__main__":
    import sys
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    out = Path(__file__).resolve().parent / "assets" / "icon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_app_icon(256).save(str(out))
    print(f"wrote {out}")
