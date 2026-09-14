"""Modern, attractive, animated UI components for Meeting Agent.

Features:
- AnimatedButton with smooth QPropertyAnimation hover and press micro-interactions
- AnimatedWallpaperWidget rendering dynamic ambient orbs and custom wallpapers
- SegmentedThemeSwitch with smooth sliding indicator pill
- AnimatedMeetingCard with glowing hover effects
- AnimatedToggleSwitch for sleek settings toggles
- Crisp vector icons and full dark/light theme awareness
"""
import math
import time
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize,
    Qt, QTimer, Property, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QDesktopServices, QFont, QFontMetrics, QIcon,
    QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .theme import WALLPAPER_PRESETS, theme
from .svg_icons import get_svg_pixmap, get_svg_icon
from .vector_icons import (
    icon_check, icon_cloud, icon_folder, icon_gear, icon_link, icon_monitor,
    icon_moon, icon_pdf, icon_play, icon_refresh, icon_search, icon_sparkle,
    icon_sun, icon_trash,
)


class PacmanWidget(QWidget):
    """The animated companion: a small chomping Pac-Man, purely vector-drawn."""

    MIN_MOUTH_DEG = 4
    MAX_MOUTH_DEG = 34

    def __init__(self, diameter: int = 36, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self._mouth_deg = self.MAX_MOUTH_DEG
        self._opening = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(110)

    def _animate(self):
        step = 5
        if self._opening:
            self._mouth_deg = min(self._mouth_deg + step, self.MAX_MOUTH_DEG)
            if self._mouth_deg >= self.MAX_MOUTH_DEG:
                self._opening = False
        else:
            self._mouth_deg = max(self._mouth_deg - step, self.MIN_MOUTH_DEG)
            if self._mouth_deg <= self.MIN_MOUTH_DEG:
                self._opening = True
        self.update()

    def stop(self):
        self._timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#FFD23F"))
        painter.setPen(Qt.NoPen)
        rect = QRectF(2, 2, self._diameter - 4, self._diameter - 4)
        start_angle = int(self._mouth_deg * 16)
        span_angle = int((360 - 2 * self._mouth_deg) * 16)
        painter.drawPie(rect, start_angle, span_angle)


def _interpolate_color(c1: QColor, c2: QColor, factor: float) -> QColor:
    """Blends between c1 and c2 by factor in [0, 1]."""
    f = max(0.0, min(1.0, factor))
    r = int(c1.red() + (c2.red() - c1.red()) * f)
    g = int(c1.green() + (c2.green() - c1.green()) * f)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * f)
    a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * f)
    return QColor(r, g, b, a)


# ==============================================================================
# Animated Wallpaper & Background Canvas
# ==============================================================================

class AnimatedWallpaperWidget(QWidget):
    """Living desktop background canvas.

    Renders either:
    1. Dynamic ambient orbs floating softly with radial glow
    2. High-res custom wallpaper with glass vignette
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self._t: float = 0.0
        self._cached_pixmap: QPixmap | None = None
        self._cached_path: str = ""

        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps silky smooth, ultra-low CPU
        self._timer.timeout.connect(self._tick)
        if theme().animations_enabled:
            self._timer.start()

        theme().theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self):
        if theme().animations_enabled and not self._timer.isActive():
            self._timer.start()
        elif not theme().animations_enabled and self._timer.isActive():
            self._timer.stop()
        self._cached_pixmap = None
        self.update()

    def _tick(self):
        if not self.isVisible():
            return
        self._t += 0.014
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        w = self.width()
        h = self.height()

        tm = theme()
        dark = tm.is_dark()
        preset = tm.current_wallpaper_preset()

        # Check if custom image wallpaper is active
        if tm.wallpaper == "custom" and tm.custom_wallpaper_path:
            p = Path(tm.custom_wallpaper_path)
            if p.exists():
                if self._cached_path != str(p) or self._cached_pixmap is None:
                    self._cached_path = str(p)
                    self._cached_pixmap = QPixmap(str(p))

                if self._cached_pixmap and not self._cached_pixmap.isNull():
                    scaled = self._cached_pixmap.scaled(
                        w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                    )
                    sx = (scaled.width() - w) // 2
                    sy = (scaled.height() - h) // 2
                    painter.drawPixmap(0, 0, scaled, sx, sy, w, h)

                    # Draw translucent glass vignette over custom image for text readability
                    tint = QColor(10, 13, 22, 190) if dark else QColor(248, 250, 252, 185)
                    painter.fillRect(0, 0, w, h, tint)
                    return

        # Procedural Animated Wallpaper Preset
        base_color = QColor(preset.base_dark if dark else preset.base_light)
        painter.fillRect(0, 0, w, h, base_color)

        orb_tuples = preset.orb_colors_dark if dark else preset.orb_colors_light
        t = self._t if tm.animations_enabled else 0.0

        # Draw 3 ambient floating orbs
        centers = [
            (w * (0.24 + 0.14 * math.sin(t * 0.7)), h * (0.32 + 0.16 * math.cos(t * 0.6)), min(w, h) * 0.46),
            (w * (0.76 + 0.15 * math.cos(t * 0.8)), h * (0.64 + 0.14 * math.sin(t * 0.9)), min(w, h) * 0.44),
            (w * (0.50 + 0.18 * math.sin(t * 0.5 + 1.2)), h * (0.46 + 0.18 * math.cos(t * 0.7 + 0.8)), min(w, h) * 0.38),
        ]

        painter.setCompositionMode(QPainter.CompositionMode_Screen if dark else QPainter.CompositionMode_Multiply)
        for i, (hex_c, alpha) in enumerate(orb_tuples):
            if i >= len(centers):
                break
            cx, cy, radius = centers[i]
            grad = QRadialGradient(QPointF(cx, cy), radius)
            c = QColor(hex_c)
            c.setAlphaF(alpha)
            grad.setColorAt(0.0, c)
            c_fade = QColor(c)
            c_fade.setAlphaF(0.0)
            grad.setColorAt(1.0, c_fade)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # Subtle noise / grid or vignette overlay
        overlay = QLinearGradient(0, 0, 0, h)
        if dark:
            overlay.setColorAt(0.0, QColor(0, 0, 0, 30))
            overlay.setColorAt(1.0, QColor(0, 0, 0, 80))
        else:
            overlay.setColorAt(0.0, QColor(255, 255, 255, 40))
            overlay.setColorAt(1.0, QColor(0, 0, 0, 20))
        painter.fillRect(0, 0, w, h, overlay)


# ==============================================================================
# Modern Animated Button
# ==============================================================================

class AnimatedButton(QPushButton):
    """A sleek button featuring fluid hover and press micro-animations.

    Variants:
    - 'primary': Gradient accent with glowing hover and soft shadow
    - 'secondary': Translucent glass pill with border
    - 'outline': Crisp accent border that fills softly on hover
    - 'danger': Soft crimson that highlights on hover
    - 'ghost': Transparent button with soft pill hover
    - 'icon': Compact round/square icon button
    """

    def __init__(
        self,
        text: str = "",
        variant: str = "secondary",
        icon: QIcon | None = None,
        parent=None,
        icon_size: int = 16,
    ):
        super().__init__(text, parent)
        self._variant = variant
        self._custom_icon = icon
        self._icon_size = icon_size
        self._hover_factor: float = 0.0
        self._press_factor: float = 0.0
        self._badge_text: str = ""

        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumHeight(38)

        # Animations
        self._hover_anim = QPropertyAnimation(self, b"hoverProgress")
        self._hover_anim.setDuration(160)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)

        self._press_anim = QPropertyAnimation(self, b"pressProgress")
        self._press_anim.setDuration(100)
        self._press_anim.setEasingCurve(QEasingCurve.OutQuad)

        theme().theme_changed.connect(self.update)

    def sizeHint(self) -> QSize:
        if self._variant == "icon":
            return QSize(38, 38)
        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(self._variant == "primary")
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.text()) if self.text() else 0
        w = tw + 34
        if self._custom_icon is not None and not self._custom_icon.isNull():
            w += self._icon_size + (10 if self.text() else 0)
        if self._badge_text:
            w += 36
        return QSize(max(w, 42), 38)

    def get_hover_progress(self) -> float:
        return self._hover_factor

    def set_hover_progress(self, val: float):
        self._hover_factor = val
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def get_press_progress(self) -> float:
        return self._press_factor

    def set_press_progress(self, val: float):
        self._press_factor = val
        self.update()

    pressProgress = Property(float, get_press_progress, set_press_progress)

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_factor)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_factor)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_anim.stop()
            self._press_anim.setStartValue(self._press_factor)
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_anim.stop()
        self._press_anim.setStartValue(self._press_factor)
        self._press_anim.setEndValue(0.0)
        self._press_anim.start()
        super().mouseReleaseEvent(event)

    def set_badge(self, text: str):
        self._badge_text = text
        self.update()

    def set_custom_icon(self, icon: QIcon | None):
        self._custom_icon = icon
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = QRectF(self.rect())
        # Slight press down inset
        inset = self._press_factor * 1.5
        rect = rect.adjusted(inset, inset, -inset, -inset)

        tm = theme()
        dark = tm.is_dark()
        hf = self._hover_factor
        r = 10.0

        if self._variant == "primary":
            # Gradient Indigo -> Purple
            c1_normal = QColor(tm.token("accent_gradient_start"))
            c2_normal = QColor(tm.token("accent_gradient_end"))
            c1_hover = QColor(tm.token("accent_primary_hover"))
            c2_hover = QColor(tm.token("accent_purple"))

            c1 = _interpolate_color(c1_normal, c1_hover, hf)
            c2 = _interpolate_color(c2_normal, c2_hover, hf)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)

            # Glow outline on hover
            if hf > 0.05:
                painter.setPen(QPen(QColor(255, 255, 255, int(80 * hf)), 1.5))
            else:
                painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(rect, r, r)
            fg_color = QColor("#FFFFFF")

        elif self._variant == "danger":
            bg_normal = QColor(239, 68, 68, 30 if dark else 20)
            bg_hover = QColor(239, 68, 68, 220)
            bg = _interpolate_color(bg_normal, bg_hover, hf)

            border_normal = QColor(239, 68, 68, 70 if dark else 60)
            border_hover = QColor(239, 68, 68, 255)
            border = _interpolate_color(border_normal, border_hover, hf)

            painter.setPen(QPen(border, 1.2))
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, r, r)

            fg_normal = QColor("#EF4444")
            fg_hover = QColor("#FFFFFF")
            fg_color = _interpolate_color(fg_normal, fg_hover, hf)

        elif self._variant == "outline":
            accent = QColor(tm.token("accent_primary"))
            bg_normal = QColor(accent.red(), accent.green(), accent.blue(), 0)
            bg_hover = QColor(accent.red(), accent.green(), accent.blue(), 45 if dark else 35)
            bg = _interpolate_color(bg_normal, bg_hover, hf)

            border_normal = QColor(accent.red(), accent.green(), accent.blue(), 130)
            border_hover = QColor(accent.red(), accent.green(), accent.blue(), 230)
            border = _interpolate_color(border_normal, border_hover, hf)

            painter.setPen(QPen(border, 1.4))
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, r, r)

            fg_color = accent if hf < 0.5 else QColor(tm.token("text_primary"))

        elif self._variant == "ghost":
            bg_normal = QColor(0, 0, 0, 0)
            bg_hover = QColor(255, 255, 255, 25 if dark else 15)
            bg = _interpolate_color(bg_normal, bg_hover, hf)

            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, r, r)
            fg_color = QColor(tm.token("text_primary"))

        elif self._variant == "icon":
            bg_normal = QColor(255, 255, 255, 12 if dark else 18)
            bg_hover = QColor(255, 255, 255, 45 if dark else 40)
            bg = _interpolate_color(bg_normal, bg_hover, hf)

            border_normal = QColor(255, 255, 255, 20 if dark else 25)
            border_hover = QColor(tm.token("accent_primary"))
            border = _interpolate_color(border_normal, border_hover, hf)

            painter.setPen(QPen(border, 1.2))
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, r, r)
            fg_color = QColor(tm.token("text_primary"))

        else:  # "secondary" / "glass"
            bg_normal = QColor(255, 255, 255, 14 if dark else 180)
            bg_hover = QColor(255, 255, 255, 32 if dark else 235)
            bg = _interpolate_color(bg_normal, bg_hover, hf)

            border_normal = QColor(255, 255, 255, 25 if dark else 40)
            border_hover = QColor(tm.token("border_hover"))
            border = _interpolate_color(border_normal, border_hover, hf)

            painter.setPen(QPen(border, 1.2))
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, r, r)
            fg_color = QColor(tm.token("text_primary"))

        # Draw content (Icon + Text)
        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(self._variant == "primary")
        painter.setFont(font)
        painter.setPen(fg_color)

        text = self.text()
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text) if text else 0
        has_icon = self._custom_icon is not None and not self._custom_icon.isNull()

        total_w = text_w
        if has_icon:
            total_w += self._icon_size + (8 if text else 0)

        start_x = rect.center().x() - total_w / 2.0
        cur_x = start_x

        if has_icon:
            icon_pixmap = self._custom_icon.pixmap(self._icon_size, self._icon_size)
            icon_y = rect.center().y() - self._icon_size / 2.0
            painter.drawPixmap(int(cur_x), int(icon_y), icon_pixmap)
            cur_x += self._icon_size + (8 if text else 0)

        if text:
            text_rect = QRectF(cur_x, rect.top(), text_w + 4, rect.height())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)

        # Optional Badge
        if self._badge_text:
            badge_font = QFont(font)
            badge_font.setPointSize(8)
            badge_font.setBold(True)
            painter.setFont(badge_font)
            bfm = QFontMetrics(badge_font)
            bw = bfm.horizontalAdvance(self._badge_text) + 8
            bh = bfm.height() + 2
            bx = rect.right() - bw - 6
            by = rect.center().y() - bh / 2.0
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(tm.token("accent_primary")))
            painter.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRectF(bx, by, bw, bh), Qt.AlignCenter, self._badge_text)


# ==============================================================================
# Animated Segmented Theme Switch (System / Dark / Light)
# ==============================================================================

class SegmentedThemeSwitch(QWidget):
    """Sleek segmented controller with smooth sliding pill indicator."""

    mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setFixedWidth(240)
        self.setCursor(Qt.PointingHandCursor)

        self._options = [
            ("system", "System", icon_monitor),
            ("dark", "Dark", icon_moon),
            ("light", "Light", icon_sun),
        ]

        # Determine active index
        cur_mode = theme().theme_mode
        self._target_index = 0
        for i, (m, _, _) in enumerate(self._options):
            if m == cur_mode:
                self._target_index = i
                break

        self._slider_pos: float = float(self._target_index)

        self._anim = QPropertyAnimation(self, b"sliderPos")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        theme().theme_changed.connect(self._sync_theme)

    def _sync_theme(self):
        cur_mode = theme().theme_mode
        for i, (m, _, _) in enumerate(self._options):
            if m == cur_mode and i != self._target_index:
                self._target_index = i
                self._animate_to(i)
                break
        self.update()

    def get_slider_pos(self) -> float:
        return self._slider_pos

    def set_slider_pos(self, val: float):
        self._slider_pos = val
        self.update()

    sliderPos = Property(float, get_slider_pos, set_slider_pos)

    def _animate_to(self, idx: int):
        self._target_index = idx
        self._anim.stop()
        self._anim.setStartValue(self._slider_pos)
        self._anim.setEndValue(float(idx))
        self._anim.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item_w = self.width() / len(self._options)
            click_idx = int(event.position().x() // item_w)
            click_idx = max(0, min(len(self._options) - 1, click_idx))
            if click_idx != self._target_index:
                self._animate_to(click_idx)
                selected_mode = self._options[click_idx][0]
                theme().theme_mode = selected_mode
                self.mode_changed.emit(selected_mode)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        tm = theme()
        dark = tm.is_dark()
        w = self.width()
        h = self.height()
        r = 10.0

        # Background track
        track_color = QColor(255, 255, 255, 14 if dark else 160)
        painter.setPen(QPen(QColor(tm.token("border_subtle")), 1.2))
        painter.setBrush(track_color)
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), r, r)

        num_items = len(self._options)
        item_w = (w - 6) / num_items
        pill_h = h - 6

        # Animated sliding pill
        pill_x = 3 + self._slider_pos * item_w
        pill_rect = QRectF(pill_x, 3, item_w, pill_h)

        pill_grad = QLinearGradient(pill_rect.topLeft(), pill_rect.bottomRight())
        pill_grad.setColorAt(0.0, QColor(tm.token("accent_gradient_start")))
        pill_grad.setColorAt(1.0, QColor(tm.token("accent_gradient_end")))

        painter.setPen(Qt.NoPen)
        painter.setBrush(pill_grad)
        painter.drawRoundedRect(pill_rect, 8.0, 8.0)

        # Draw Labels & Icons
        font = QFont(self.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        for i, (mode, label, icon_fn) in enumerate(self._options):
            center_x = 3 + i * item_w + item_w / 2.0
            dist = abs(self._slider_pos - i)
            active_ratio = max(0.0, 1.0 - dist)

            # Active item text is pure white, inactive is secondary text
            text_color = _interpolate_color(
                QColor(tm.token("text_secondary")),
                QColor("#FFFFFF"),
                active_ratio
            )

            icon = icon_fn(color=text_color.name(), size=14)
            pix = icon.pixmap(14, 14)

            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(label)
            total_content_w = 14 + 5 + tw
            start_x = center_x - total_content_w / 2.0

            painter.drawPixmap(int(start_x), int((h - 14) / 2.0), pix)

            painter.setPen(text_color)
            painter.drawText(
                QRectF(start_x + 19, 0, tw + 4, h),
                Qt.AlignVCenter | Qt.AlignLeft,
                label,
            )


# ==============================================================================
# Animated Toggle Switch (iOS / Modern macOS style)
# ==============================================================================

class AnimatedToggleSwitch(QWidget):
    """Modern fluid sliding toggle switch."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked
        self._thumb_pos: float = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"thumbPos")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        if checked != self._checked:
            self._checked = checked
            self._animate_thumb(1.0 if checked else 0.0)
            self.toggled.emit(self._checked)

    def get_thumb_pos(self) -> float:
        return self._thumb_pos

    def set_thumb_pos(self, val: float):
        self._thumb_pos = val
        self.update()

    thumbPos = Property(float, get_thumb_pos, set_thumb_pos)

    def _animate_thumb(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(target)
        self._anim.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        tm = theme()
        dark = tm.is_dark()
        w = self.width()
        h = self.height()
        r = h / 2.0

        # Background track interpolation
        bg_off = QColor(255, 255, 255, 30 if dark else 70)
        bg_on = QColor(tm.token("accent_primary"))
        track_bg = _interpolate_color(bg_off, bg_on, self._thumb_pos)

        painter.setPen(Qt.NoPen)
        painter.setBrush(track_bg)
        painter.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # Sliding thumb
        thumb_diameter = h - 6
        thumb_x = 3 + self._thumb_pos * (w - thumb_diameter - 6)
        thumb_rect = QRectF(thumb_x, 3, thumb_diameter, thumb_diameter)

        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(thumb_rect)


# ==============================================================================
# Animated Meeting Card Widget (Recent Meetings item)
# ==============================================================================

class AnimatedMeetingCard(QWidget):
    """Frosted glass card representing one recorded meeting.

    Displays:
    - Platform icon badge (Google Meet, Zoom, Teams, Manual)
    - Meeting title and formatted timestamp
    - Action buttons: 'Open PDF', 'Copy Link', 'Delete'
    - Smooth hover highlight animation
    """

    open_pdf_clicked = Signal()
    copy_link_clicked = Signal()
    delete_clicked = Signal()

    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = record
        self._hover_factor: float = 0.0

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(68)

        self._anim = QPropertyAnimation(self, b"hoverProgress")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # 1. Platform badge icon
        platform = record.get("platform", "Manual")
        badge = self._create_platform_badge(platform)
        layout.addWidget(badge)

        # 2. Meeting Title & Timestamp Column
        meta_col = QVBoxLayout()
        meta_col.setSpacing(3)

        title_text = record.get("title") or f"{platform} Meeting"
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet("font-weight: 700; font-size: 11pt;")
        meta_col.addWidget(self.title_lbl)

        time_row = QHBoxLayout()
        time_row.setSpacing(6)
        cal_icon = QLabel()
        cal_icon.setPixmap(get_svg_pixmap("google_calendar", size=14))
        created_at_fmt = self._format_timestamp(record.get("created_at", ""))
        self.time_lbl = QLabel(created_at_fmt)
        self.time_lbl.setStyleSheet(f"font-size: 9pt; color: {theme().token('text_secondary')};")
        time_row.addWidget(cal_icon)
        time_row.addWidget(self.time_lbl)
        time_row.addStretch()
        meta_col.addLayout(time_row)

        layout.addLayout(meta_col)
        layout.addStretch()

        # 3. Action Buttons
        self.open_btn = AnimatedButton("Open PDF", variant="outline", icon=icon_pdf(size=15), icon_size=15)
        self.open_btn.clicked.connect(self.open_pdf_clicked.emit)

        self.copy_btn = AnimatedButton("Copy Link", variant="secondary", icon=icon_link(size=15), icon_size=15)
        self.copy_btn.clicked.connect(self._on_copy_link)

        self.del_btn = AnimatedButton("", variant="danger", icon=icon_trash(size=15), icon_size=15)
        self.del_btn.setFixedWidth(38)
        self.del_btn.setToolTip("Delete meeting record and PDF")
        self.del_btn.clicked.connect(self.delete_clicked.emit)

        layout.addWidget(self.open_btn)
        layout.addWidget(self.copy_btn)
        layout.addWidget(self.del_btn)

        theme().theme_changed.connect(self._update_styles)
        self._update_styles()

    def _create_platform_badge(self, platform: str) -> QLabel:
        lbl = QLabel()
        lbl.setFixedSize(42, 42)
        lbl.setAlignment(Qt.AlignCenter)

        plat_lower = platform.lower()
        if "meet" in plat_lower:
            lbl.setPixmap(get_svg_pixmap("google_meet", size=30))
            lbl.setStyleSheet("""
                QLabel {
                    background-color: rgba(255, 255, 255, 0.90);
                    border-radius: 11px;
                    border: 1px solid rgba(0, 0, 0, 0.08);
                }
            """)
        elif "zoom" in plat_lower:
            lbl.setPixmap(get_svg_pixmap("zoom", size=30))
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #2D8CFF;
                    border-radius: 11px;
                }
            """)
        else:
            # Manual or generic recording
            lbl.setPixmap(get_svg_pixmap("play", color="#FFFFFF", size=20))
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #6366F1;
                    border-radius: 11px;
                }
            """)
        return lbl

    def _format_timestamp(self, iso: str) -> str:
        try:
            from datetime import datetime
            return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y • %I:%M %p")
        except Exception:
            return iso

    def _on_copy_link(self):
        url = self.record.get("pdf_url") or ""
        QApplication.clipboard().setText(url)
        self.copy_btn.setText("✓ Copied!")
        self.copy_btn.set_custom_icon(icon_check(size=15))
        QTimer.singleShot(2000, self._reset_copy_btn)
        self.copy_link_clicked.emit()

    def _reset_copy_btn(self):
        self.copy_btn.setText("Copy Link")
        self.copy_btn.set_custom_icon(icon_link(size=15))

    def _update_styles(self):
        tm = theme()
        self.title_lbl.setStyleSheet(f"font-weight: 700; font-size: 11pt; color: {tm.token('text_primary')};")
        self.time_lbl.setStyleSheet(f"font-size: 9pt; color: {tm.token('text_secondary')};")
        self.update()

    def get_hover_progress(self) -> float:
        return self._hover_factor

    def set_hover_progress(self, val: float):
        self._hover_factor = val
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_factor)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._anim.stop()
        self._anim.setStartValue(self._hover_factor)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        tm = theme()
        dark = tm.is_dark()
        hf = self._hover_factor

        # Card background blending
        c_norm = tm.get_color("bg_card")
        c_hov = tm.get_color("bg_card_hover")
        bg = _interpolate_color(c_norm, c_hov, hf)

        b_norm = tm.get_color("border_card")
        b_hov = tm.get_color("border_hover")
        border = _interpolate_color(b_norm, b_hov, hf)

        painter.setPen(QPen(border, 1.3))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 14.0, 14.0)


# ==============================================================================
# Wallpaper Selector Modal / Drawer
# ==============================================================================

class WallpaperPickerModal(QWidget):
    """Visual gallery of wallpaper presets + Custom image chooser."""

    wallpaper_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Background Wallpaper")
        self.setFixedSize(580, 420)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        self.header_lbl = QLabel("Choose Background Wallpaper")
        self.header_lbl.setStyleSheet("font-size: 14pt; font-weight: 700;")
        layout.addWidget(self.header_lbl)

        self.sub_lbl = QLabel("Select a dynamic animated theme or upload a custom image.")
        self.sub_lbl.setStyleSheet(f"font-size: 9.5pt; color: {theme().token('text_secondary')};")
        layout.addWidget(self.sub_lbl)

        # Preset Cards Grid
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(12)

        for pid, preset in WALLPAPER_PRESETS.items():
            btn = self._build_preset_card(preset)
            grid_layout.addWidget(btn)

        layout.addLayout(grid_layout)

        # Custom Wallpaper Section
        self.custom_card = QWidget()
        c_layout = QHBoxLayout(self.custom_card)
        c_layout.setContentsMargins(14, 12, 14, 12)

        self.custom_path_lbl = QLabel(
            theme().custom_wallpaper_path or "No custom wallpaper selected (PNG, JPG, WebP supported)"
        )
        self.custom_path_lbl.setStyleSheet(f"color: {theme().token('text_secondary')}; font-size: 9pt;")
        c_layout.addWidget(self.custom_path_lbl, 1)

        browse_btn = AnimatedButton("Choose Image...", variant="primary", icon=icon_folder(size=16), icon_size=16)
        browse_btn.clicked.connect(self._browse_custom_image)
        c_layout.addWidget(browse_btn)

        layout.addWidget(self.custom_card)

        # Toggle Background Animation
        anim_row = QHBoxLayout()
        self.anim_lbl = QLabel("✨ Enable Background Ambient Motion")
        self.anim_lbl.setStyleSheet("font-weight: 600; font-size: 10pt;")
        self.anim_toggle = AnimatedToggleSwitch(checked=theme().animations_enabled)
        self.anim_toggle.toggled.connect(self._on_toggle_animation)
        anim_row.addWidget(self.anim_lbl)
        anim_row.addStretch()
        anim_row.addWidget(self.anim_toggle)
        layout.addLayout(anim_row)

        layout.addStretch()

        close_btn = AnimatedButton("Done", variant="secondary")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

        theme().theme_changed.connect(self._update_theme)
        self._update_theme()

    def _update_theme(self):
        tm = theme()
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {tm.token('bg_window')};
                color: {tm.token('text_primary')};
            }}
        """)
        self.header_lbl.setStyleSheet(f"font-size: 14pt; font-weight: 700; color: {tm.token('text_primary')};")
        self.sub_lbl.setStyleSheet(f"font-size: 9.5pt; color: {tm.token('text_secondary')};")
        self.custom_card.setStyleSheet(f"""
            QWidget {{
                background: {tm.token('bg_card')};
                border: 1px solid {tm.token('border_card')};
                border-radius: 12px;
            }}
        """)
        self.custom_path_lbl.setStyleSheet(f"color: {tm.token('text_secondary')}; font-size: 9pt; border: none; background: transparent;")
        self.anim_lbl.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {tm.token('text_primary')}; border: none; background: transparent;")

    def _build_preset_card(self, preset) -> QWidget:
        card = QPushButton()
        card.setFixedSize(120, 110)
        card.setCursor(Qt.PointingHandCursor)
        active = (theme().wallpaper == preset.id)

        border = theme().token("accent_primary") if active else theme().token("border_card")
        card.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {preset.base_dark}, stop:1 {preset.orb_colors_dark[0][0]});
                border: {3 if active else 1}px solid {border};
                border-radius: 12px;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 9.5pt;
                padding-bottom: 10px;
            }}
            QPushButton:hover {{
                border: 2px solid {theme().token('accent_primary')};
            }}
        """)
        card.setText(f"\n\n{preset.name}")
        card.clicked.connect(lambda: self._select_preset(preset.id))
        return card

    def _select_preset(self, pid: str):
        theme().wallpaper = pid
        self.wallpaper_selected.emit(pid)
        self.close()

    def _browse_custom_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Wallpaper Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            theme().custom_wallpaper_path = path
            theme().wallpaper = "custom"
            self.custom_path_lbl.setText(path)
            self.wallpaper_selected.emit("custom")

    def _on_toggle_animation(self, enabled: bool):
        theme().animations_enabled = enabled
