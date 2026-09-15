"""Redesigned Settings Dialog with modern tabbed layout, theme support,
wallpaper selector, password visibility toggles, folder browsing, and fluid animations.
"""
from pathlib import Path
from PySide6.QtCore import QRectF, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from . import config as config_module
from . import google_auth
from .theme import WALLPAPER_PRESETS, theme
from .svg_icons import (
    get_svg_pixmap, icon_gmail, icon_google, icon_google_calendar,
    icon_google_drive, icon_reload, icon_setting,
)
from .vector_icons import (
    icon_check, icon_cloud, icon_eye, icon_eye_off, icon_folder,
    icon_monitor, icon_moon, icon_palette, icon_sparkle, icon_sun,
)
from .widgets import (
    AnimatedButton, AnimatedToggleSwitch, SegmentedThemeSwitch, _interpolate_color,
)

SECRET_FIELDS = {"gemini_api_key", "r2_secret_access_key"}

GOOGLE_CLOUD_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"


class GoogleConnectWorker(QThread):
    """Runs the blocking OAuth browser flow off the GUI thread.

    get_credentials() opens a browser and blocks on a local HTTP server
    until the consent redirect lands -- that can take a while (or hang, if
    the browser fails to launch), and running it on the main thread freezes
    the whole app ("Not Responding") for the entire wait. Reproduced live.
    """

    succeeded = Signal()
    failed = Signal(str)

    def run(self):
        try:
            google_auth.get_credentials()
        except Exception as e:
            self.failed.emit(str(e))
        else:
            self.succeeded.emit()


class GoogleSetupDialog(QDialog):
    """One-time guide for pointing the app at a user's own Google OAuth client.

    Shown the first time "Connect Account" is clicked and no client secret is
    on disk yet, instead of a bare FileNotFoundError -- walks the user to
    Cloud Console and lets them pick the downloaded JSON with a file dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect Google Account")
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Connect your own Google account")
        title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        layout.addWidget(title)

        body = QLabel(
            "This app uses your own Google OAuth client, so your Gmail/Drive/"
            "Calendar access is never shared with anyone else. One-time setup:\n\n"
            "1. Open Google Cloud Console and create (or reuse) an OAuth client "
            "of type \"Desktop app\".\n"
            "2. Download its JSON file.\n"
            "3. Choose that file below."
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"font-size: 9.5pt; color: {theme().token('text_secondary')};")
        layout.addWidget(body)

        open_console_btn = AnimatedButton("Open Google Cloud Console", variant="secondary")
        open_console_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GOOGLE_CLOUD_CREDENTIALS_URL))
        )
        layout.addWidget(open_console_btn)

        choose_btn = AnimatedButton("Choose credentials.json...", variant="primary")
        choose_btn.clicked.connect(self._choose_file)
        layout.addWidget(choose_btn)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("color: #EF4444; font-size: 9pt;")
        layout.addWidget(self.status_lbl)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select your Google OAuth client JSON",
            "",
            "JSON files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        try:
            google_auth.install_client_secret(Path(path))
        except ValueError as e:
            self.status_lbl.setText(str(e))
            return
        self.accept()


class PasswordLineEdit(QWidget):
    """Line edit with an integrated eye toggle button for password visibility."""

    def __init__(self, text: str = "", placeholder: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.edit = QLineEdit(text)
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(38)

        self.toggle_btn = AnimatedButton("", variant="icon", icon=icon_eye(size=16), icon_size=16)
        self.toggle_btn.setFixedSize(38, 38)
        self.toggle_btn.setToolTip("Toggle password visibility")
        self.toggle_btn.clicked.connect(self._toggle)

        layout.addWidget(self.edit, 1)
        layout.addWidget(self.toggle_btn)

        self._visible = False
        self._update_styles()
        theme().theme_changed.connect(self._update_styles)

    def _toggle(self):
        self._visible = not self._visible
        if self._visible:
            self.edit.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.set_custom_icon(icon_eye_off(size=16))
        else:
            self.edit.setEchoMode(QLineEdit.Password)
            self.toggle_btn.set_custom_icon(icon_eye(size=16))

    def text(self) -> str:
        return self.edit.text()

    def setText(self, val: str):
        self.edit.setText(val)

    def _update_styles(self):
        tm = theme()
        self.edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tm.token('bg_input')};
                color: {tm.token('text_primary')};
                border: 1px solid {tm.token('border_card')};
                border-radius: 9px;
                padding: 8px 12px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {tm.token('border_focus')};
            }}
        """)


class SettingsDialog(QDialog):
    """Modern Settings modal with categorized navigation, live theme switching,
    custom wallpaper picker, and elegant styling.
    """

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PacNotes Settings")
        self.resize(840, 620)
        self.setMinimumSize(780, 560)
        self.cfg = dict(cfg)

        self._init_ui()
        self._load_values()
        theme().theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_box = QLabel()
        icon_box.setFixedSize(42, 42)
        icon_box.setPixmap(get_svg_pixmap("setting", color="#6366F1", size=26))
        icon_box.setAlignment(Qt.AlignCenter)
        icon_box.setStyleSheet(f"""
            QLabel {{
                background: {theme().token('bg_card')};
                border: 1px solid {theme().token('border_card')};
                border-radius: 10px;
            }}
        """)
        header_row.addWidget(icon_box)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_lbl = QLabel("Meeting Agent Settings")
        self.title_lbl.setStyleSheet("font-size: 15pt; font-weight: 800;")
        self.subtitle_lbl = QLabel("Configure AI models, storage, email delivery, and appearance.")
        self.subtitle_lbl.setStyleSheet(f"font-size: 9.5pt; color: {theme().token('text_secondary')};")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.subtitle_lbl)
        header_row.addLayout(title_col)
        header_row.addStretch()

        # Segmented theme switch in header
        self.header_theme_switch = SegmentedThemeSwitch()
        header_row.addWidget(self.header_theme_switch)

        main_layout.addLayout(header_row)

        # Body: Sidebar Tabs + Stacked Content
        body_layout = QHBoxLayout()
        body_layout.setSpacing(18)

        # Left Sidebar Navigation
        self.nav_list = QVBoxLayout()
        self.nav_list.setSpacing(6)

        self.tab_buttons: list[AnimatedButton] = []
        tabs = [
            ("AI & Models", icon_sparkle),
            ("Storage & Cloud", icon_cloud),
            ("Google & Email", lambda color=None, size=17: icon_google(size=size)),
            ("Appearance & Wallpaper", icon_palette),
        ]

        for i, (title, icon_fn) in enumerate(tabs):
            btn = AnimatedButton(title, variant="ghost", icon=icon_fn(size=17), icon_size=17)
            btn.setFixedHeight(42)
            btn.setStyleSheet("text-align: left; padding-left: 12px;")
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            self.tab_buttons.append(btn)
            self.nav_list.addWidget(btn)

        self.nav_list.addStretch()

        sidebar_container = QWidget()
        sidebar_container.setFixedWidth(210)
        sidebar_container.setLayout(self.nav_list)
        body_layout.addWidget(sidebar_container)

        # Vertical Divider line
        v_line = QFrame()
        v_line.setFrameShape(QFrame.VLine)
        v_line.setStyleSheet(f"color: {theme().token('border_card')};")
        body_layout.addWidget(v_line)

        # Right Stacked Content
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_ai_tab())
        self.stack.addWidget(self._create_storage_tab())
        self.stack.addWidget(self._create_email_tab())
        self.stack.addWidget(self._create_appearance_tab())

        body_layout.addWidget(self.stack, 1)
        main_layout.addLayout(body_layout, 1)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #EF4444; font-weight: 600; font-size: 9.5pt;")
        bottom_bar.addWidget(self.status_lbl)
        bottom_bar.addStretch()

        cancel_btn = AnimatedButton("Cancel", variant="secondary")
        cancel_btn.clicked.connect(self.reject)

        save_btn = AnimatedButton("Save Changes", variant="primary", icon=icon_check(size=16), icon_size=16)
        save_btn.clicked.connect(self._save)

        bottom_bar.addWidget(cancel_btn)
        bottom_bar.addWidget(save_btn)
        main_layout.addLayout(bottom_bar)

        self._switch_tab(0)

    def _switch_tab(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.tab_buttons):
            if i == idx:
                btn._variant = "secondary"
            else:
                btn._variant = "ghost"
            btn.update()

    # --------------------------------------------------------------------------
    # Tab 1: AI & Models
    # --------------------------------------------------------------------------
    def _create_ai_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(16)

        # Gemini API Key
        layout.addWidget(self._section_title("Gemini AI Configuration"))
        layout.addWidget(self._field_label("Gemini API Key"))
        self.gemini_key_edit = PasswordLineEdit(placeholder="Enter your Google Gemini API key")
        layout.addWidget(self.gemini_key_edit)

        # Gemini Model
        layout.addWidget(self._field_label("Gemini Model"))
        self.gemini_model_combo = QComboBox()
        self.gemini_model_combo.setEditable(True)
        self.gemini_model_combo.addItems([
            "gemini-3.6-flash",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-pro",
        ])
        self.gemini_model_combo.setMinimumHeight(38)
        layout.addWidget(self.gemini_model_combo)

        # Whisper Model
        layout.addWidget(self._section_title("Speech Transcription"))
        layout.addWidget(self._field_label("Whisper Model (Local Audio Transcription)"))
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.whisper_combo.setMinimumHeight(38)
        layout.addWidget(self.whisper_combo)

        whisper_hint = QLabel("💡 'small' is recommended: fast inference with excellent transcription accuracy.")
        whisper_hint.setStyleSheet(f"font-size: 8.5pt; color: {theme().token('text_muted')};")
        layout.addWidget(whisper_hint)

        layout.addStretch()
        return widget

    # --------------------------------------------------------------------------
    # Tab 2: Storage & Cloud
    # --------------------------------------------------------------------------
    def _create_storage_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(16)

        layout.addWidget(self._section_title("Storage Backend"))

        # Backend Selector Cards (R2 vs Drive)
        backend_row = QHBoxLayout()
        self.r2_card = QPushButton("Cloudflare R2\n(S3-compatible, Zero Egress)")
        self.r2_card.setFixedHeight(60)
        self.r2_card.setCursor(Qt.PointingHandCursor)
        self.r2_card.clicked.connect(lambda: self._select_storage_backend("r2"))

        self.drive_card = QPushButton("Google Drive\n(Shared OAuth Storage)")
        self.drive_card.setFixedHeight(60)
        self.drive_card.setCursor(Qt.PointingHandCursor)
        self.drive_card.setIcon(icon_google_drive(size=22))
        self.drive_card.setIconSize(QSize(22, 22))
        self.drive_card.clicked.connect(lambda: self._select_storage_backend("drive"))

        backend_row.addWidget(self.r2_card)
        backend_row.addWidget(self.drive_card)
        layout.addLayout(backend_row)

        # R2 Fields Stack
        self.r2_fields_widget = QWidget()
        r2_layout = QVBoxLayout(self.r2_fields_widget)
        r2_layout.setContentsMargins(0, 0, 0, 0)
        r2_layout.setSpacing(10)

        r2_layout.addWidget(self._field_label("R2 Account ID"))
        self.r2_account_id_edit = QLineEdit()
        self.r2_account_id_edit.setMinimumHeight(38)
        r2_layout.addWidget(self.r2_account_id_edit)

        r2_layout.addWidget(self._field_label("R2 Access Key ID"))
        self.r2_access_key_edit = QLineEdit()
        self.r2_access_key_edit.setMinimumHeight(38)
        r2_layout.addWidget(self.r2_access_key_edit)

        r2_layout.addWidget(self._field_label("R2 Secret Access Key"))
        self.r2_secret_key_edit = PasswordLineEdit(placeholder="Cloudflare R2 Secret Access Key")
        r2_layout.addWidget(self.r2_secret_key_edit)

        r2_layout.addWidget(self._field_label("R2 Bucket Name"))
        self.r2_bucket_edit = QLineEdit()
        self.r2_bucket_edit.setMinimumHeight(38)
        r2_layout.addWidget(self.r2_bucket_edit)

        layout.addWidget(self.r2_fields_widget)

        # Drive Fields Stack
        self.drive_info_widget = QWidget()
        drive_layout = QVBoxLayout(self.drive_info_widget)
        drive_layout.setContentsMargins(0, 0, 0, 0)
        drive_card = QLabel("Google Drive is active. Generated PDF notes and transcripts will be automatically uploaded to your connected Google Drive.")
        drive_card.setWordWrap(True)
        drive_card.setStyleSheet(f"""
            QLabel {{
                background: {theme().token('bg_card')};
                border: 1px solid {theme().token('border_card')};
                border-radius: 10px;
                padding: 14px;
                color: {theme().token('text_primary')};
            }}
        """)
        drive_layout.addWidget(drive_card)
        layout.addWidget(self.drive_info_widget)

        # Local Output Directory
        layout.addWidget(self._section_title("Local Notes Output Directory"))
        out_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setMinimumHeight(38)
        browse_btn = AnimatedButton("Browse...", variant="secondary", icon=icon_folder(size=16), icon_size=16)
        browse_btn.clicked.connect(self._browse_output_dir)
        open_folder_btn = AnimatedButton("Open Folder", variant="outline")
        open_folder_btn.clicked.connect(self._open_output_dir)

        out_row.addWidget(self.output_dir_edit, 1)
        out_row.addWidget(browse_btn)
        out_row.addWidget(open_folder_btn)
        layout.addLayout(out_row)

        layout.addStretch()
        return widget

    def _select_storage_backend(self, backend: str):
        self.cfg["storage_backend"] = backend
        active_style = f"""
            QPushButton {{
                background: {theme().token('bg_card_hover')};
                border: 2px solid {theme().token('accent_primary')};
                border-radius: 10px;
                font-weight: 700;
                color: {theme().token('text_primary')};
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background: {theme().token('bg_card')};
                border: 1px solid {theme().token('border_card')};
                border-radius: 10px;
                font-weight: 500;
                color: {theme().token('text_secondary')};
            }}
        """
        if backend == "r2":
            self.r2_card.setStyleSheet(active_style)
            self.drive_card.setStyleSheet(inactive_style)
            self.r2_fields_widget.show()
            self.drive_info_widget.hide()
        else:
            self.r2_card.setStyleSheet(inactive_style)
            self.drive_card.setStyleSheet(active_style)
            self.r2_fields_widget.hide()
            self.drive_info_widget.show()

    def _browse_output_dir(self):
        # DontUseNativeDialog: native Win32 dialogs crash under a PyInstaller
        # --onefile bootloader on Windows; see _browse_custom_wallpaper below.
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.output_dir_edit.text(),
            options=QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog,
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _open_output_dir(self):
        p = Path(self.output_dir_edit.text())
        if p.exists():
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    # --------------------------------------------------------------------------
    # Tab 3: Google & Email
    # --------------------------------------------------------------------------
    def _create_email_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(16)

        layout.addWidget(self._section_title("Google Account Integration"))

        # Google Account Connection Card
        google_card = QWidget()
        google_card.setStyleSheet(f"""
            QWidget {{
                background: {theme().token('bg_card')};
                border: 1px solid {theme().token('border_card')};
                border-radius: 12px;
            }}
        """)
        g_layout = QHBoxLayout(google_card)
        g_layout.setContentsMargins(16, 14, 16, 14)
        g_layout.setSpacing(14)

        g_logo = QLabel()
        g_logo.setPixmap(get_svg_pixmap("google", size=32))
        g_layout.addWidget(g_logo)

        g_info_col = QVBoxLayout()
        self.google_status_lbl = QLabel()
        self.google_status_lbl.setStyleSheet("font-weight: 700; font-size: 11pt;")
        g_sub = QLabel("Provides Gmail delivery, Google Calendar lookup, and Drive backup.")
        g_sub.setStyleSheet(f"font-size: 9pt; color: {theme().token('text_secondary')};")
        g_info_col.addWidget(self.google_status_lbl)
        g_info_col.addWidget(g_sub)
        g_layout.addLayout(g_info_col, 1)

        self.connect_google_btn = AnimatedButton("Connect Account", variant="primary", icon=icon_google(size=16), icon_size=16)
        self.connect_google_btn.clicked.connect(self._connect_google)
        g_layout.addWidget(self.connect_google_btn)
        layout.addWidget(google_card)

        # Recipient Email
        email_sec = QHBoxLayout()
        email_sec.setSpacing(8)
        gmail_icon = QLabel()
        gmail_icon.setPixmap(get_svg_pixmap("gmail", size=20))
        email_sec.addWidget(gmail_icon)
        email_sec.addWidget(self._section_title("Email Delivery (Gmail)"))
        email_sec.addStretch()
        layout.addLayout(email_sec)

        layout.addWidget(self._field_label("Recipient Email Address"))
        self.recipient_email_edit = QLineEdit()
        self.recipient_email_edit.setPlaceholderText("your-email@example.com")
        self.recipient_email_edit.setMinimumHeight(38)
        layout.addWidget(self.recipient_email_edit)

        # Toggle: Auto Email
        auto_row = QHBoxLayout()
        auto_text_col = QVBoxLayout()
        auto_lbl = QLabel("Auto Email PDF")
        auto_lbl.setStyleSheet("font-weight: 600; font-size: 10pt;")
        auto_desc = QLabel("Automatically send an email with the PDF summary upon meeting completion.")
        auto_desc.setStyleSheet(f"font-size: 8.5pt; color: {theme().token('text_secondary')};")
        auto_text_col.addWidget(auto_lbl)
        auto_text_col.addWidget(auto_desc)
        self.auto_email_toggle = AnimatedToggleSwitch()
        auto_row.addLayout(auto_text_col, 1)
        auto_row.addWidget(self.auto_email_toggle)
        layout.addLayout(auto_row)

        # Toggle: Keep Audio
        audio_row = QHBoxLayout()
        audio_text_col = QVBoxLayout()
        audio_lbl = QLabel("Keep Audio File")
        audio_lbl.setStyleSheet("font-weight: 600; font-size: 10pt;")
        audio_desc = QLabel("Retain raw audio recording (.wav) after transcription completes.")
        audio_desc.setStyleSheet(f"font-size: 8.5pt; color: {theme().token('text_secondary')};")
        audio_text_col.addWidget(audio_lbl)
        audio_text_col.addWidget(audio_desc)
        self.keep_audio_toggle = AnimatedToggleSwitch()
        audio_row.addLayout(audio_text_col, 1)
        audio_row.addWidget(self.keep_audio_toggle)
        layout.addLayout(audio_row)

        layout.addStretch()
        return widget

    def _refresh_google_status(self):
        connected = google_auth.is_connected()
        if connected:
            self.google_status_lbl.setText("🟢 Google Account: Connected")
            self.google_status_lbl.setStyleSheet("color: #10B981; font-weight: 700; font-size: 11pt;")
            self.connect_google_btn.setText("Reconnect")
            self.connect_google_btn.set_custom_icon(icon_reload(color="#FFFFFF", size=15))
            self.connect_google_btn._variant = "secondary"
        else:
            self.google_status_lbl.setText("🟡 Google Account: Not Connected")
            self.google_status_lbl.setStyleSheet("color: #F59E0B; font-weight: 700; font-size: 11pt;")
            self.connect_google_btn.setText("Connect Account")
            self.connect_google_btn.set_custom_icon(icon_google(size=16))
            self.connect_google_btn._variant = "primary"
        self.connect_google_btn.update()

    def _connect_google(self):
        if not google_auth.has_client_secret():
            if GoogleSetupDialog(self).exec() != QDialog.Accepted:
                return  # user closed the setup dialog without choosing a file

        self.connect_google_btn.setEnabled(False)
        self.connect_google_btn.setText("Waiting for browser...")
        self.connect_google_btn.update()

        self._google_worker = GoogleConnectWorker(self)
        self._google_worker.succeeded.connect(self._on_google_connect_succeeded)
        self._google_worker.failed.connect(self._on_google_connect_failed)
        self._google_worker.start()

    def _on_google_connect_succeeded(self):
        self.connect_google_btn.setEnabled(True)
        self._refresh_google_status()
        QMessageBox.information(self, "Success", "Google account connected successfully!")

    def _on_google_connect_failed(self, message: str):
        self.connect_google_btn.setEnabled(True)
        self._refresh_google_status()
        QMessageBox.warning(self, "Google connection failed", message)

    # --------------------------------------------------------------------------
    # Tab 4: Appearance & Wallpaper
    # --------------------------------------------------------------------------
    def _create_appearance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(16)

        layout.addWidget(self._section_title("Color Theme"))
        theme_desc = QLabel("Choose your visual mode. System automatically matches your OS preference.")
        theme_desc.setStyleSheet(f"font-size: 9pt; color: {theme().token('text_secondary')};")
        layout.addWidget(theme_desc)

        self.tab_theme_switch = SegmentedThemeSwitch()
        layout.addWidget(self.tab_theme_switch)

        layout.addWidget(self._section_title("Background Wallpaper"))
        wall_desc = QLabel("Select an animated ambient theme or choose a custom desktop wallpaper image.")
        wall_desc.setStyleSheet(f"font-size: 9pt; color: {theme().token('text_secondary')};")
        layout.addWidget(wall_desc)

        # Preset Buttons Grid
        grid_row = QHBoxLayout()
        grid_row.setSpacing(10)
        for pid, preset in WALLPAPER_PRESETS.items():
            card = QPushButton(f"\n{preset.name}")
            card.setFixedSize(110, 80)
            card.setCursor(Qt.PointingHandCursor)
            active = (theme().wallpaper == pid)
            border = theme().token("accent_primary") if active else theme().token("border_card")
            card.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {preset.base_dark}, stop:1 {preset.orb_colors_dark[0][0]});
                    border: {3 if active else 1}px solid {border};
                    border-radius: 10px;
                    color: #FFFFFF;
                    font-weight: 700;
                    font-size: 8.5pt;
                }}
            """)
            card.clicked.connect(lambda _, p=pid: self._choose_wallpaper_preset(p))
            grid_row.addWidget(card)
        layout.addLayout(grid_row)

        # Custom Wallpaper Row
        custom_row = QHBoxLayout()
        self.wall_path_lbl = QLabel(theme().custom_wallpaper_path or "No custom wallpaper chosen")
        self.wall_path_lbl.setStyleSheet(f"font-size: 9pt; color: {theme().token('text_secondary')};")
        custom_btn = AnimatedButton("Choose Custom Image...", variant="secondary", icon=icon_folder(size=16), icon_size=16)
        custom_btn.clicked.connect(self._browse_custom_wallpaper)
        custom_row.addWidget(self.wall_path_lbl, 1)
        custom_row.addWidget(custom_btn)
        layout.addLayout(custom_row)

        # Toggle Animation
        anim_row = QHBoxLayout()
        anim_col = QVBoxLayout()
        anim_title = QLabel("✨ Background Ambient Motion")
        anim_title.setStyleSheet("font-weight: 600; font-size: 10pt;")
        anim_sub = QLabel("Gentle floating light orbs in the background.")
        anim_sub.setStyleSheet(f"font-size: 8.5pt; color: {theme().token('text_secondary')};")
        anim_col.addWidget(anim_title)
        anim_col.addWidget(anim_sub)
        self.anim_toggle = AnimatedToggleSwitch(checked=theme().animations_enabled)
        self.anim_toggle.toggled.connect(self._toggle_animations)
        anim_row.addLayout(anim_col, 1)
        anim_row.addWidget(self.anim_toggle)
        layout.addLayout(anim_row)

        layout.addStretch()
        return widget

    def _choose_wallpaper_preset(self, pid: str):
        theme().wallpaper = pid
        self.cfg["wallpaper"] = pid

    def _browse_custom_wallpaper(self):
        # DontUseNativeDialog: the native Win32 file dialog's COM/shell
        # integration crashes when invoked from a PyInstaller --onefile
        # bootloader on Windows; Qt's own dialog sidesteps it.
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Wallpaper Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            theme().custom_wallpaper_path = path
            theme().wallpaper = "custom"
            self.cfg["wallpaper"] = "custom"
            self.cfg["custom_wallpaper_path"] = path
            self.wall_path_lbl.setText(path)

    def _toggle_animations(self, enabled: bool):
        theme().animations_enabled = enabled
        self.cfg["enable_animations"] = enabled

    # --------------------------------------------------------------------------
    # Helpers & Sync
    # --------------------------------------------------------------------------
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        if not hasattr(self, "_section_labels"):
            self._section_labels = []
        self._section_labels.append(lbl)
        lbl.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {theme().token('text_primary')}; margin-top: 6px;")
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        if not hasattr(self, "_field_labels"):
            self._field_labels = []
        self._field_labels.append(lbl)
        lbl.setStyleSheet(f"font-size: 9pt; font-weight: 600; color: {theme().token('text_secondary')};")
        return lbl

    def _load_values(self):
        self.gemini_key_edit.setText(str(self.cfg.get("gemini_api_key", "")))
        self.gemini_model_combo.setCurrentText(str(self.cfg.get("gemini_model", "gemini-3.6-flash")))
        self.whisper_combo.setCurrentText(str(self.cfg.get("whisper_model", "small")))

        backend = self.cfg.get("storage_backend", "r2")
        self._select_storage_backend(backend)

        self.r2_account_id_edit.setText(str(self.cfg.get("r2_account_id", "")))
        self.r2_access_key_edit.setText(str(self.cfg.get("r2_access_key_id", "")))
        self.r2_secret_key_edit.setText(str(self.cfg.get("r2_secret_access_key", "")))
        self.r2_bucket_edit.setText(str(self.cfg.get("r2_bucket_name", "")))
        self.output_dir_edit.setText(str(self.cfg.get("output_dir", str(Path.home() / "MeetingNotes"))))

        self.recipient_email_edit.setText(str(self.cfg.get("recipient_email", "")))
        self.auto_email_toggle.setChecked(bool(self.cfg.get("auto_email", True)))
        self.keep_audio_toggle.setChecked(bool(self.cfg.get("keep_audio", False)))

        self._refresh_google_status()

    def _on_theme_changed(self):
        tm = theme()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tm.token('bg_window')};
                color: {tm.token('text_primary')};
            }}
            QLabel {{
                color: {tm.token('text_primary')};
            }}
            QLineEdit {{
                background-color: {tm.token('bg_input')};
                color: {tm.token('text_primary')};
                border: 1px solid {tm.token('border_card')};
                border-radius: 9px;
                padding: 8px 12px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border: 1.5px solid {tm.token('border_focus')};
            }}
            QComboBox {{
                background-color: {tm.token('bg_input')};
                color: {tm.token('text_primary')};
                border: 1px solid {tm.token('border_card')};
                border-radius: 9px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QComboBox:focus {{
                border: 1.5px solid {tm.token('border_focus')};
            }}
            QComboBox QAbstractItemView {{
                background-color: {tm.token('bg_card_solid')};
                color: {tm.token('text_primary')};
                selection-background-color: {tm.token('accent_primary')};
                selection-color: #FFFFFF;
                border: 1px solid {tm.token('border_card')};
                border-radius: 8px;
            }}
        """)
        self.title_lbl.setStyleSheet(f"font-size: 15pt; font-weight: 800; color: {tm.token('text_primary')};")
        self.subtitle_lbl.setStyleSheet(f"font-size: 9.5pt; color: {tm.token('text_secondary')};")

        for lbl in getattr(self, "_section_labels", []):
            lbl.setStyleSheet(f"font-size: 11.5pt; font-weight: 700; color: {tm.token('text_primary')}; margin-top: 6px;")
        for lbl in getattr(self, "_field_labels", []):
            lbl.setStyleSheet(f"font-size: 9pt; font-weight: 600; color: {tm.token('text_secondary')};")

    def _save(self):
        self.cfg["gemini_api_key"] = self.gemini_key_edit.text().strip()
        self.cfg["gemini_model"] = self.gemini_model_combo.currentText().strip()
        self.cfg["whisper_model"] = self.whisper_combo.currentText().strip()

        self.cfg["r2_account_id"] = self.r2_account_id_edit.text().strip()
        self.cfg["r2_access_key_id"] = self.r2_access_key_edit.text().strip()
        self.cfg["r2_secret_access_key"] = self.r2_secret_key_edit.text().strip()
        self.cfg["r2_bucket_name"] = self.r2_bucket_edit.text().strip()
        self.cfg["output_dir"] = self.output_dir_edit.text().strip()

        self.cfg["recipient_email"] = self.recipient_email_edit.text().strip()
        self.cfg["auto_email"] = self.auto_email_toggle.isChecked()
        self.cfg["keep_audio"] = self.keep_audio_toggle.isChecked()

        missing = config_module.missing_fields(self.cfg)
        if missing:
            self.status_lbl.setText(f"Missing required fields: {', '.join(missing)}")
            return
        if not google_auth.is_connected():
            self.status_lbl.setText("Please connect your Google account before saving.")
            return

        config_module.save_config(self.cfg)
        self.accept()
