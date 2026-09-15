"""Redesigned Dashboard Window:
- Dynamic wallpaper background with living ambient motion
- Glassmorphic top bar with brand badge and 1-click theme switcher (System / Dark / Light)
- Quick stats summary cards
- Real-time search and filtering of recent meetings
- Animated cards with smooth hover transitions, 'Open PDF', 'Copy Link' with animated feedback, and 'Delete'
- Quick wallpaper selector dialog
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from . import meetings
from .icons import app_icon
from .settings_dialog import SettingsDialog
from .theme import theme
from .svg_icons import (
    get_svg_pixmap, icon_play, icon_reload, icon_setting,
)
from .vector_icons import (
    icon_check, icon_cloud, icon_link, icon_pdf,
    icon_search, icon_sparkle, icon_trash, icon_palette,
)
from .widgets import (
    AnimatedButton, AnimatedMeetingCard, AnimatedWallpaperWidget,
    PacmanWidget, SegmentedThemeSwitch, WallpaperPickerModal,
)


def _format_created_at(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y • %I:%M %p")
    except ValueError:
        return iso


class GlassCard(QWidget):
    """Frosted glass container with rounded corners and subtle border."""

    def __init__(self, parent=None, radius: float = 14.0):
        super().__init__(parent)
        self._radius = radius
        theme().theme_changed.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tm = theme()

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = tm.get_color("bg_surface")
        border = tm.get_color("border_card")

        painter.setPen(QPen(border, 1.2))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, self._radius, self._radius)


class DashboardWindow(QMainWindow):
    """Redesigned modern dashboard for Meeting Agent."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("PacNotes Studio")
        self.setWindowIcon(app_icon())
        self.resize(960, 680)
        self.setMinimumSize(780, 520)

        self._all_records: list[dict] = []
        self._filter_query: str = ""

        self._init_ui()
        theme().theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed()
        self.refresh()

    def _init_ui(self):
        # The central widget is the animated living wallpaper canvas
        self.wallpaper_canvas = AnimatedWallpaperWidget(self)
        self.setCentralWidget(self.wallpaper_canvas)

        # Layout inside the wallpaper canvas
        root_layout = QVBoxLayout(self.wallpaper_canvas)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(14)

        # ======================================================================
        # 1. Top Glass Header Bar
        # ======================================================================
        self.header_card = GlassCard(radius=16.0)
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(14)

        # Mascot + App Title
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        self.pacman = PacmanWidget(32)
        brand_row.addWidget(self.pacman)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self.brand_title = QLabel("PacNotes")
        self.brand_title.setStyleSheet("font-size: 13pt; font-weight: 800;")
        self.brand_subtitle = QLabel("🟢 Ready to Record")
        self.brand_subtitle.setStyleSheet(f"font-size: 8.5pt; color: #10B981; font-weight: 600;")
        title_col.addWidget(self.brand_title)
        title_col.addWidget(self.brand_subtitle)
        brand_row.addLayout(title_col)
        header_layout.addLayout(brand_row)

        header_layout.addStretch()

        # Action Group: [Start Meeting] [Wallpaper] [Theme Switcher] [Settings]
        self.new_btn = AnimatedButton("New Meeting", variant="primary", icon=icon_play(size=16), icon_size=16)
        self.new_btn.clicked.connect(self._on_new_meeting)
        header_layout.addWidget(self.new_btn)

        self.wallpaper_btn = AnimatedButton("Wallpaper", variant="secondary", icon=icon_palette(size=16), icon_size=16)
        self.wallpaper_btn.clicked.connect(self._on_open_wallpaper_picker)
        header_layout.addWidget(self.wallpaper_btn)

        self.theme_switch = SegmentedThemeSwitch()
        header_layout.addWidget(self.theme_switch)

        self.settings_btn = AnimatedButton("", variant="icon", icon=icon_setting(size=18), icon_size=18)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._on_settings)
        header_layout.addWidget(self.settings_btn)

        root_layout.addWidget(self.header_card)

        # ======================================================================
        # 2. Quick Metric / Summary Chips
        # ======================================================================
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.stat_meetings = self._build_stat_card("📊 Total Meetings", "0 recorded", "#6366F1")
        self.stat_storage = self._build_stat_card("☁️ Cloud Storage", "Cloudflare R2", "#06B6D4")
        self.stat_model = self._build_stat_card("🧠 AI Intelligence", "Gemini 3.6 Flash", "#8B5CF6")

        stats_row.addWidget(self.stat_meetings)
        stats_row.addWidget(self.stat_storage)
        stats_row.addWidget(self.stat_model)
        root_layout.addLayout(stats_row)

        # ======================================================================
        # 3. Main Recent Meetings Glass Panel
        # ======================================================================
        self.content_card = GlassCard(radius=16.0)
        content_layout = QVBoxLayout(self.content_card)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(12)

        # Section Header + Search & Filter Bar
        subhead_row = QHBoxLayout()
        subhead_row.setSpacing(12)

        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        self.sec_title = QLabel("Recent Meetings")
        self.sec_title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        self.count_badge = QLabel("0 sessions")
        self.count_badge.setStyleSheet(f"""
            QLabel {{
                background: {theme().token('bg_pill')};
                color: {theme().token('text_secondary')};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 8.5pt;
                font-weight: 600;
            }}
        """)
        title_box.addWidget(self.sec_title)
        title_box.addWidget(self.count_badge)
        subhead_row.addLayout(title_box)

        subhead_row.addStretch()

        # Search Bar
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search meetings by title or platform...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(280)
        self.search_edit.setMinimumHeight(34)
        self.search_edit.textChanged.connect(self._on_search_changed)
        subhead_row.addWidget(self.search_edit)

        self.refresh_btn = AnimatedButton("", variant="icon", icon=icon_reload(size=16), icon_size=16)
        self.refresh_btn.setToolTip("Refresh meetings list")
        self.refresh_btn.clicked.connect(self.refresh)
        subhead_row.addWidget(self.refresh_btn)

        content_layout.addLayout(subhead_row)

        # Scrollable Meeting Cards Container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        content_layout.addWidget(self.scroll_area, 1)

        # Empty State Container
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 40, 20, 40)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignCenter)

        empty_icon = QLabel("🎙️")
        empty_icon.setStyleSheet("font-size: 34pt;")
        empty_icon.setAlignment(Qt.AlignCenter)
        self.empty_title = QLabel("No meetings recorded yet")
        self.empty_title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_sub = QLabel("Start a manual recording or join Google Meet/Zoom to automatically capture notes.")
        self.empty_sub.setStyleSheet(f"font-size: 9.5pt; color: {theme().token('text_secondary')};")
        self.empty_sub.setAlignment(Qt.AlignCenter)

        empty_start_btn = AnimatedButton("Start First Meeting", variant="primary", icon=icon_play(size=16), icon_size=16)
        empty_start_btn.setFixedWidth(190)
        empty_start_btn.clicked.connect(self._on_new_meeting)

        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_sub)
        empty_layout.addWidget(empty_start_btn, 0, Qt.AlignCenter)
        content_layout.addWidget(self.empty_widget)

        root_layout.addWidget(self.content_card, 1)

    def _build_stat_card(self, title: str, val: str, accent_color: str) -> QWidget:
        card = GlassCard(radius=12.0)
        card.setFixedHeight(64)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(2)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"font-size: 8.5pt; font-weight: 600; color: {accent_color};")
        v_lbl = QLabel(val)
        v_lbl.setObjectName("stat_val")
        v_lbl.setStyleSheet(f"font-size: 11pt; font-weight: 700; color: {theme().token('text_primary')};")

        layout.addWidget(t_lbl)
        layout.addWidget(v_lbl)
        return card

    def _update_stats(self, count: int):
        # Meetings
        v1 = self.stat_meetings.findChild(QLabel, "stat_val")
        if v1:
            v1.setText(f"{count} {'session' if count == 1 else 'sessions'}")

        # Storage
        backend = self.controller.cfg.get("storage_backend", "r2")
        backend_name = "Cloudflare R2" if backend == "r2" else "Google Drive"
        v2 = self.stat_storage.findChild(QLabel, "stat_val")
        if v2:
            v2.setText(f"{backend_name} (Active)")

        # AI Model
        model = self.controller.cfg.get("gemini_model", "gemini-3.6-flash")
        v3 = self.stat_model.findChild(QLabel, "stat_val")
        if v3:
            v3.setText(model)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _on_theme_changed(self):
        tm = theme()
        self.brand_title.setStyleSheet(f"font-size: 13pt; font-weight: 800; color: {tm.token('text_primary')};")
        self.sec_title.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {tm.token('text_primary')};")
        self.empty_title.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {tm.token('text_primary')};")
        self.empty_sub.setStyleSheet(f"font-size: 9.5pt; color: {tm.token('text_secondary')};")

        # Update stat values
        for stat_card in [self.stat_meetings, self.stat_storage, self.stat_model]:
            val_lbl = stat_card.findChild(QLabel, "stat_val")
            if val_lbl:
                val_lbl.setStyleSheet(f"font-size: 11pt; font-weight: 700; color: {tm.token('text_primary')};")

        self.settings_btn.set_custom_icon(icon_setting(color=tm.token('text_primary'), size=18))
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.set_custom_icon(icon_reload(color=tm.token('text_secondary'), size=16))
        self.wallpaper_btn.set_custom_icon(icon_palette(color=tm.token('text_primary'), size=16))

        self.count_badge.setStyleSheet(f"""
            QLabel {{
                background: {tm.token('bg_pill')};
                color: {tm.token('text_secondary')};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 8.5pt;
                font-weight: 600;
            }}
        """)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tm.token('bg_input')};
                color: {tm.token('text_primary')};
                border: 1px solid {tm.token('border_card')};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 9.5pt;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {tm.token('border_focus')};
            }}
        """)
        self.update()

    def _on_search_changed(self, text: str):
        self._filter_query = text.strip().lower()
        self._render_cards()

    def refresh(self):
        self._all_records = meetings.list_meetings()
        self._render_cards()
        self._update_stats(len(self._all_records))

    def _render_cards(self):
        # Clear existing card widgets
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Filter records
        filtered = []
        for r in self._all_records:
            if not self._filter_query:
                filtered.append(r)
            else:
                title = (r.get("title") or "").lower()
                plat = (r.get("platform") or "").lower()
                date_str = (r.get("created_at") or "").lower()
                if self._filter_query in title or self._filter_query in plat or self._filter_query in date_str:
                    filtered.append(r)

        self.count_badge.setText(f"{len(filtered)} {'session' if len(filtered) == 1 else 'sessions'}")

        if not filtered:
            self.scroll_area.hide()
            self.empty_widget.show()
            if self._filter_query:
                self.empty_title.setText("No matching meetings")
                self.empty_sub.setText(f"No recordings match '{self._filter_query}'. Clear search to view all.")
            else:
                self.empty_title.setText("No meetings recorded yet")
                self.empty_sub.setText("Start a manual recording or join Google Meet/Zoom to automatically capture notes.")
        else:
            self.empty_widget.hide()
            self.scroll_area.show()
            for record in filtered:
                card = AnimatedMeetingCard(record)
                card.open_pdf_clicked.connect(lambda p=record["pdf_path"]: self._open_pdf(p))
                card.delete_clicked.connect(lambda m=record["id"]: self._on_delete(m))
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _open_pdf(self, pdf_path: str):
        path = Path(pdf_path)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, "File Not Found", f"PDF not found on disk:\n{pdf_path}")

    def _on_delete(self, meeting_id: str):
        reply = QMessageBox.question(
            self,
            "Delete Meeting",
            "Delete this meeting notes report and its PDF file? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            meetings.delete_meeting(meeting_id)
            self.refresh()

    def _on_new_meeting(self):
        self.controller._on_manual_trigger()

    def _on_settings(self):
        dialog = SettingsDialog(self.controller.cfg, self)
        if dialog.exec() == QDialog.Accepted:
            self.controller.cfg = dialog.cfg
            self._update_stats(len(self._all_records))

    def _on_open_wallpaper_picker(self):
        picker = WallpaperPickerModal(self)
        picker.show()
