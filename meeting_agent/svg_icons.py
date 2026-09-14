"""SVG Icon Loader and Tinting Engine for Meeting Agent.

Loads vector SVGs from the 'svg' directory with caching and real-time color tinting.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

_PIXMAP_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def _get_svg_dir() -> Path:
    candidates = []
    # PyInstaller onefile extracts --add-data under sys._MEIPASS, not next to
    # __file__ -- check that first so a frozen build finds the bundled SVGs.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "svg")
    candidates += [
        Path(__file__).resolve().parent.parent / "svg",
        Path(__file__).resolve().parent / "svg",
        Path(__file__).resolve().parent / "assets" / "svg",
        Path("svg").resolve(),
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return candidates[0]


SVG_DIR = _get_svg_dir()

SVG_FILENAMES = {
    "dots_vertical": "dots-6-vertical-svgrepo-com.svg",
    "camera": "camera-minimalistic-svgrepo-com.svg",
    "stop_circle": "media-stop-circle-svgrepo-com.svg",
    "play": "play-svgrepo-com.svg",
    "pause": "pause-svgrepo-com.svg",
    "reload": "reload-svgrepo-com.svg",
    "setting": "setting-svgrepo-com.svg",
    "google": "google-logo-search-new-svgrepo-com.svg",
    "google_meet": "google-logo-meet-new-svgrepo-com.svg",
    "google_drive": "google-logo-drive-new-svgrepo-com.svg",
    "google_calendar": "calendar-google-logo-new-svgrepo-com.svg",
    "gmail": "new-logo-gmail-svgrepo-com.svg",
    "zoom": "zoom-svgrepo-com.svg",
    "resize_handle": "resize-handle-svgrepo-com.svg",
}


def get_svg_pixmap(name: str, color: QColor | str | None = None, size: int = 24) -> QPixmap:
    """Load an SVG as a crisp QPixmap, optionally tinting monochromatic icons."""
    filename = SVG_FILENAMES.get(name, name)
    file_path = SVG_DIR / filename
    if not file_path.exists():
        # Fallback to empty pixmap if not found
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        return pix

    color_key = color.name() if isinstance(color, QColor) else (color or "none")
    cache_key = (name, color_key, size)
    if cache_key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[cache_key]

    raw_icon = QIcon(str(file_path))
    base_pix = raw_icon.pixmap(size, size)

    if color is not None:
        tinted = QPixmap(size, size)
        tinted.fill(Qt.transparent)
        p = QPainter(tinted)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(0, 0, base_pix)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.fillRect(tinted.rect(), QColor(color))
        p.end()
        result = tinted
    else:
        result = base_pix

    _PIXMAP_CACHE[cache_key] = result
    return result


def get_svg_icon(name: str, color: QColor | str | None = None, size: int = 24) -> QIcon:
    """Return a QIcon wrapping the rendered SVG."""
    return QIcon(get_svg_pixmap(name, color=color, size=size))


# Named helpers
def icon_dots_vertical(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    return get_svg_icon("dots_vertical", color=color, size=size)


def icon_camera(color: QColor | str = "#FFFFFF", size: int = 24) -> QIcon:
    return get_svg_icon("camera", color=color, size=size)


def icon_stop_circle(color: QColor | str = "#FFFFFF", size: int = 24) -> QIcon:
    return get_svg_icon("stop_circle", color=color, size=size)


def icon_play(color: QColor | str = "#FFFFFF", size: int = 24) -> QIcon:
    return get_svg_icon("play", color=color, size=size)


def icon_pause(color: QColor | str = "#FFFFFF", size: int = 24) -> QIcon:
    return get_svg_icon("pause", color=color, size=size)


def icon_reload(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    return get_svg_icon("reload", color=color, size=size)


def icon_setting(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    return get_svg_icon("setting", color=color, size=size)


# Full-color brand logos
def icon_google(size: int = 24) -> QIcon:
    return get_svg_icon("google", color=None, size=size)


def icon_google_meet(size: int = 24) -> QIcon:
    return get_svg_icon("google_meet", color=None, size=size)


def icon_google_drive(size: int = 24) -> QIcon:
    return get_svg_icon("google_drive", color=None, size=size)


def icon_google_calendar(size: int = 24) -> QIcon:
    return get_svg_icon("google_calendar", color=None, size=size)


def icon_gmail(size: int = 24) -> QIcon:
    return get_svg_icon("gmail", color=None, size=size)


def icon_zoom(size: int = 24) -> QIcon:
    return get_svg_icon("zoom", color=None, size=size)


def icon_resize_handle(color: QColor | str = "#94A3B8", size: int = 24) -> QIcon:
    return get_svg_icon("resize_handle", color=color, size=size)
