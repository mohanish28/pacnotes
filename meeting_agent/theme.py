"""Theme and Wallpaper management system for Meeting Agent.

Supports:
- Modes: System, Dark, Light
- Live dynamic updates across all windows
- Wallpaper themes: Aurora, Midnight, Sunset, Minimal, Custom Image
- Animated ambient orbs configuration
- Comprehensive design tokens for typography, surfaces, borders, and accents
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from . import config as config_module


@dataclass
class WallpaperPreset:
    id: str
    name: str
    description: str
    base_dark: str
    base_light: str
    # List of (hex_color, opacity, speed_x, speed_y)
    orb_colors_dark: list[tuple[str, float]]
    orb_colors_light: list[tuple[str, float]]


WALLPAPER_PRESETS: dict[str, WallpaperPreset] = {
    "aurora": WallpaperPreset(
        id="aurora",
        name="Aurora Glow",
        description="Deep cosmic indigo and vibrant violet-cyan nebula waves",
        base_dark="#0A0D18",
        base_light="#EEF2FF",
        orb_colors_dark=[("#4F46E5", 0.40), ("#8B5CF6", 0.35), ("#06B6D4", 0.30)],
        orb_colors_light=[("#818CF8", 0.30), ("#C084FC", 0.25), ("#67E8F9", 0.25)],
    ),
    "midnight": WallpaperPreset(
        id="midnight",
        name="Midnight Obsidian",
        description="Deep starry slate with subtle amethyst and sapphire mist",
        base_dark="#06080F",
        base_light="#F1F5F9",
        orb_colors_dark=[("#1E1B4B", 0.50), ("#311042", 0.40), ("#0F172A", 0.45)],
        orb_colors_light=[("#94A3B8", 0.25), ("#A5B4FC", 0.20), ("#CBD5E1", 0.25)],
    ),
    "sunset": WallpaperPreset(
        id="sunset",
        name="Sunset Horizon",
        description="Warm twilight gradient with glowing rose, amber, and purple",
        base_dark="#13091B",
        base_light="#FFF7ED",
        orb_colors_dark=[("#831843", 0.40), ("#701A75", 0.35), ("#7C2D12", 0.30)],
        orb_colors_light=[("#FDA4AF", 0.30), ("#F0ABFC", 0.25), ("#FDBA74", 0.25)],
    ),
    "minimal": WallpaperPreset(
        id="minimal",
        name="Clean Glass",
        description="Ultra-clean, subtle architectural glassmorphism",
        base_dark="#0D1117",
        base_light="#F8FAFC",
        orb_colors_dark=[("#1E293B", 0.25), ("#334155", 0.20), ("#1E1B4B", 0.15)],
        orb_colors_light=[("#E2E8F0", 0.40), ("#F1F5F9", 0.35), ("#E0E7FF", 0.30)],
    ),
}


class ThemeManager(QObject):
    """Central singleton theme coordinator emitting live theme changes."""
    theme_changed = Signal()

    _instance = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._cfg = config_module.load_config()
        self._theme_mode: str = self._cfg.get("theme", "system")  # "system", "dark", "light"
        self._wallpaper: str = self._cfg.get("wallpaper", "aurora")
        self._custom_wallpaper_path: str = self._cfg.get("custom_wallpaper_path", "")
        self._animations_enabled: bool = bool(self._cfg.get("enable_animations", True))

    @property
    def theme_mode(self) -> str:
        return self._theme_mode

    @theme_mode.setter
    def theme_mode(self, mode: str):
        if mode in ("system", "dark", "light") and mode != self._theme_mode:
            self._theme_mode = mode
            self._cfg["theme"] = mode
            config_module.save_config(self._cfg)
            self.theme_changed.emit()

    @property
    def wallpaper(self) -> str:
        return self._wallpaper

    @wallpaper.setter
    def wallpaper(self, val: str):
        if val != self._wallpaper:
            self._wallpaper = val
            self._cfg["wallpaper"] = val
            config_module.save_config(self._cfg)
            self.theme_changed.emit()

    @property
    def custom_wallpaper_path(self) -> str:
        return self._custom_wallpaper_path

    @custom_wallpaper_path.setter
    def custom_wallpaper_path(self, path: str):
        self._custom_wallpaper_path = path
        self._cfg["custom_wallpaper_path"] = path
        config_module.save_config(self._cfg)
        self.theme_changed.emit()

    @property
    def animations_enabled(self) -> bool:
        return self._animations_enabled

    @animations_enabled.setter
    def animations_enabled(self, val: bool):
        self._animations_enabled = val
        self._cfg["enable_animations"] = val
        config_module.save_config(self._cfg)
        self.theme_changed.emit()

    def is_dark(self) -> bool:
        if self._theme_mode == "dark":
            return True
        if self._theme_mode == "light":
            return False
        # System theme detection
        app = QApplication.instance()
        if app is not None:
            hints = app.styleHints()
            if hasattr(hints, "colorScheme"):
                return hints.colorScheme() == Qt.ColorScheme.Dark
            palette = app.palette()
            window_bg = palette.color(QPalette.Window)
            return window_bg.lightness() < 128
        return True

    def get_color(self, name: str) -> QColor:
        val = self.token(name)
        if val.startswith("rgba"):
            # Parse rgba(r, g, b, a)
            parts = val[val.find("(") + 1 : val.find(")")].split(",")
            r = int(parts[0].strip())
            g = int(parts[1].strip())
            b = int(parts[2].strip())
            a = float(parts[3].strip())
            return QColor(r, g, b, int(a * 255))
        return QColor(val)

    def token(self, name: str) -> str:
        """Fetch color token string for current effective theme."""
        dark = self.is_dark()
        tokens = {
            # Surfaces & Backgrounds
            "bg_window": "#0A0D16" if dark else "#F8FAFC",
            "bg_surface": "rgba(16, 20, 31, 0.82)" if dark else "rgba(255, 255, 255, 0.88)",
            "bg_surface_solid": "#10141F" if dark else "#FFFFFF",
            "bg_card": "rgba(24, 28, 44, 0.72)" if dark else "rgba(255, 255, 255, 0.92)",
            "bg_card_hover": "rgba(35, 41, 64, 0.85)" if dark else "rgba(241, 245, 249, 0.98)",
            "bg_card_solid": "#181C2C" if dark else "#FFFFFF",
            "bg_input": "rgba(11, 14, 24, 0.80)" if dark else "rgba(255, 255, 255, 0.95)",
            "bg_pill": "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.06)",
            "bg_pill_hover": "rgba(255, 255, 255, 0.15)" if dark else "rgba(0, 0, 0, 0.10)",

            # Borders
            "border_subtle": "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.08)",
            "border_card": "rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.10)",
            "border_hover": "rgba(139, 92, 246, 0.50)" if dark else "rgba(99, 102, 241, 0.45)",
            "border_focus": "#6366F1",

            # Typography
            "text_primary": "#F8FAFC" if dark else "#0F172A",
            "text_secondary": "#94A3B8" if dark else "#475569",
            "text_muted": "#64748B" if dark else "#94A3B8",
            "text_inverse": "#0F172A" if dark else "#FFFFFF",

            # Primary Brand Accents
            "accent_primary": "#6366F1",
            "accent_primary_hover": "#4F46E5",
            "accent_gradient_start": "#6366F1",
            "accent_gradient_end": "#8B5CF6",
            "accent_purple": "#A855F7",
            "accent_cyan": "#06B6D4",
            "accent_emerald": "#10B981",
            "accent_rose": "#F43F5E",
            "accent_amber": "#F59E0B",
            "accent_danger": "#EF4444",
            "accent_danger_hover": "#DC2626",
            "accent_danger_bg": "rgba(239, 68, 68, 0.15)" if dark else "rgba(239, 68, 68, 0.10)",

            # Shadows
            "shadow_color": "rgba(0, 0, 0, 0.35)" if dark else "rgba(0, 0, 0, 0.08)",
            "shadow_glow": "rgba(99, 102, 241, 0.25)",
        }
        return tokens.get(name, "#6366F1")

    def current_wallpaper_preset(self) -> WallpaperPreset:
        if self._wallpaper in WALLPAPER_PRESETS:
            return WALLPAPER_PRESETS[self._wallpaper]
        return WALLPAPER_PRESETS["aurora"]


def theme() -> ThemeManager:
    return ThemeManager.instance()
