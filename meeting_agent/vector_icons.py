"""Crisp vector-drawn icons using QPainter for PySide6.

Zero external asset dependencies, sharp at any DPI/scale, customizable colors.
"""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _create_pixmap(size: int = 24) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    return pixmap, painter


def icon_sun(color: QColor | str = "#F59E0B", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    center = size / 2.0
    r = size * 0.22
    p.drawEllipse(QPointF(center, center), r, r)

    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    num_rays = 8
    ray_in = size * 0.32
    ray_out = size * 0.44
    for i in range(num_rays):
        angle = i * (2 * math.pi / num_rays)
        x1 = center + ray_in * math.cos(angle)
        y1 = center + ray_in * math.sin(angle)
        x2 = center + ray_out * math.cos(angle)
        y2 = center + ray_out * math.sin(angle)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    p.end()
    return QIcon(pixmap)


def icon_moon(color: QColor | str = "#818CF8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)

    path1 = QPainterPath()
    path1.addEllipse(QRectF(size * 0.15, size * 0.15, size * 0.7, size * 0.7))
    path2 = QPainterPath()
    path2.addEllipse(QRectF(size * 0.32, size * 0.10, size * 0.65, size * 0.65))

    moon_path = path1.subtracted(path2)
    p.drawPath(moon_path)
    p.end()
    return QIcon(pixmap)


def icon_monitor(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    screen_rect = QRectF(size * 0.14, size * 0.16, size * 0.72, size * 0.52)
    p.drawRoundedRect(screen_rect, size * 0.08, size * 0.08)

    # Stand
    p.drawLine(QPointF(size * 0.5, size * 0.68), QPointF(size * 0.5, size * 0.82))
    p.drawLine(QPointF(size * 0.32, size * 0.82), QPointF(size * 0.68, size * 0.82))

    p.end()
    return QIcon(pixmap)


def icon_gear(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    center = size / 2.0
    r_inner = size * 0.16
    r_teeth = size * 0.34
    p.drawEllipse(QPointF(center, center), r_inner, r_inner)

    teeth = 6
    for i in range(teeth):
        angle = i * (2 * math.pi / teeth)
        x1 = center + (r_inner + size * 0.04) * math.cos(angle)
        y1 = center + (r_inner + size * 0.04) * math.sin(angle)
        x2 = center + r_teeth * math.cos(angle)
        y2 = center + r_teeth * math.sin(angle)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    p.end()
    return QIcon(pixmap)


def icon_search(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.09, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    p.drawEllipse(QRectF(size * 0.16, size * 0.16, size * 0.44, size * 0.44))
    p.drawLine(QPointF(size * 0.52, size * 0.52), QPointF(size * 0.82, size * 0.82))

    p.end()
    return QIcon(pixmap)


def icon_play(color: QColor | str = "#FFFFFF", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)

    path = QPainterPath()
    path.moveTo(size * 0.28, size * 0.2)
    path.lineTo(size * 0.78, size * 0.5)
    path.lineTo(size * 0.28, size * 0.8)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return QIcon(pixmap)


def icon_pdf(color: QColor | str = "#EF4444", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.22, size * 0.15)
    path.lineTo(size * 0.58, size * 0.15)
    path.lineTo(size * 0.78, size * 0.35)
    path.lineTo(size * 0.78, size * 0.85)
    path.lineTo(size * 0.22, size * 0.85)
    path.closeSubpath()
    p.drawPath(path)

    p.drawLine(QPointF(size * 0.58, size * 0.15), QPointF(size * 0.58, size * 0.35))
    p.drawLine(QPointF(size * 0.58, size * 0.35), QPointF(size * 0.78, size * 0.35))

    p.drawLine(QPointF(size * 0.35, size * 0.52), QPointF(size * 0.65, size * 0.52))
    p.drawLine(QPointF(size * 0.35, size * 0.66), QPointF(size * 0.55, size * 0.66))

    p.end()
    return QIcon(pixmap)


def icon_link(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.09, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path1 = QPainterPath()
    path1.moveTo(size * 0.45, size * 0.32)
    path1.lineTo(size * 0.60, size * 0.32)
    path1.arcTo(QRectF(size * 0.45, size * 0.18, size * 0.38, size * 0.38), 90, -180)
    path1.lineTo(size * 0.45, size * 0.56)

    path2 = QPainterPath()
    path2.moveTo(size * 0.55, size * 0.68)
    path2.lineTo(size * 0.40, size * 0.68)
    path2.arcTo(QRectF(size * 0.17, size * 0.44, size * 0.38, size * 0.38), 270, -180)
    path2.lineTo(size * 0.55, size * 0.44)

    p.drawPath(path1)
    p.drawPath(path2)
    p.drawLine(QPointF(size * 0.36, size * 0.50), QPointF(size * 0.64, size * 0.50))

    p.end()
    return QIcon(pixmap)


def icon_trash(color: QColor | str = "#EF4444", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.28, size * 0.34)
    path.lineTo(size * 0.32, size * 0.84)
    path.lineTo(size * 0.68, size * 0.84)
    path.lineTo(size * 0.72, size * 0.34)
    p.drawPath(path)

    p.drawLine(QPointF(size * 0.2, size * 0.34), QPointF(size * 0.8, size * 0.34))
    p.drawLine(QPointF(size * 0.42, size * 0.22), QPointF(size * 0.58, size * 0.22))
    p.drawLine(QPointF(size * 0.42, size * 0.22), QPointF(size * 0.42, size * 0.34))
    p.drawLine(QPointF(size * 0.58, size * 0.22), QPointF(size * 0.58, size * 0.34))

    p.drawLine(QPointF(size * 0.44, size * 0.46), QPointF(size * 0.44, size * 0.72))
    p.drawLine(QPointF(size * 0.56, size * 0.56), QPointF(size * 0.56, size * 0.72))

    p.end()
    return QIcon(pixmap)


def icon_check(color: QColor | str = "#10B981", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.22, size * 0.52)
    path.lineTo(size * 0.42, size * 0.74)
    path.lineTo(size * 0.78, size * 0.28)
    p.drawPath(path)

    p.end()
    return QIcon(pixmap)


def icon_palette(color: QColor | str = "#A855F7", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    rect = QRectF(size * 0.14, size * 0.14, size * 0.72, size * 0.72)
    p.drawEllipse(rect)

    p.setBrush(c)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(size * 0.34, size * 0.36), size * 0.06, size * 0.06)
    p.drawEllipse(QPointF(size * 0.54, size * 0.30), size * 0.06, size * 0.06)
    p.drawEllipse(QPointF(size * 0.68, size * 0.48), size * 0.06, size * 0.06)
    p.drawEllipse(QPointF(size * 0.50, size * 0.66), size * 0.08, size * 0.08)

    p.end()
    return QIcon(pixmap)


def icon_eye(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.15, size * 0.5)
    path.quadTo(size * 0.5, size * 0.18, size * 0.85, size * 0.5)
    path.quadTo(size * 0.5, size * 0.82, size * 0.15, size * 0.5)
    p.drawPath(path)

    p.setBrush(c)
    p.drawEllipse(QPointF(size * 0.5, size * 0.5), size * 0.14, size * 0.14)

    p.end()
    return QIcon(pixmap)


def icon_eye_off(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    icon = icon_eye(color, size)
    pixmap = icon.pixmap(size, size)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), size * 0.09, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(size * 0.2, size * 0.2), QPointF(size * 0.8, size * 0.8))
    p.end()
    return QIcon(pixmap)


def icon_folder(color: QColor | str = "#F59E0B", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.15, size * 0.3)
    path.lineTo(size * 0.40, size * 0.3)
    path.lineTo(size * 0.48, size * 0.40)
    path.lineTo(size * 0.85, size * 0.40)
    path.lineTo(size * 0.85, size * 0.78)
    path.lineTo(size * 0.15, size * 0.78)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return QIcon(pixmap)


def icon_refresh(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.09, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    rect = QRectF(size * 0.2, size * 0.2, size * 0.6, size * 0.6)
    p.drawArc(rect, 45 * 16, 270 * 16)

    p.drawLine(QPointF(size * 0.52, size * 0.15), QPointF(size * 0.76, size * 0.24))
    p.drawLine(QPointF(size * 0.76, size * 0.24), QPointF(size * 0.70, size * 0.45))

    p.end()
    return QIcon(pixmap)


def icon_cloud(color: QColor | str = "#38BDF8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    pen = QPen(c, size * 0.08, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    path = QPainterPath()
    path.moveTo(size * 0.25, size * 0.7)
    path.lineTo(size * 0.75, size * 0.7)
    path.arcTo(QRectF(size * 0.60, size * 0.45, size * 0.28, size * 0.28), 270, 180)
    path.arcTo(QRectF(size * 0.35, size * 0.25, size * 0.36, size * 0.36), 30, 150)
    path.arcTo(QRectF(size * 0.15, size * 0.44, size * 0.26, size * 0.26), 90, 180)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return QIcon(pixmap)


def icon_sparkle(color: QColor | str = "#818CF8", size: int = 24) -> QIcon:
    pixmap, p = _create_pixmap(size)
    c = QColor(color)
    p.setPen(Qt.NoPen)
    p.setBrush(c)

    center = size / 2.0
    r_outer = size * 0.38
    r_inner = size * 0.10

    path = QPainterPath()
    for i in range(8):
        angle = i * (math.pi / 4.0)
        r = r_outer if i % 2 == 0 else r_inner
        x = center + r * math.cos(angle)
        y = center + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return QIcon(pixmap)
