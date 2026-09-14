"""All PySide6 UI: tray icon, popup, floating control bar, settings dialog, controller."""
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, Signal, QThread
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout,
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QSizeGrip, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import calendar_lookup
from . import config as config_module
from . import google_auth
from . import screenshotter
from .detector import MeetingDetector
from .icons import ACCENT_YELLOW, BG_BOTTOM, BG_TOP, INK_WHITE, app_icon
from .pipeline import PipelineError, run_pipeline
from .recorder import Recorder

PANEL_RADIUS = 18


def _paint_rounded_panel(widget: QWidget, top: QColor, bottom: QColor):
    """Fill `widget`'s background with a rounded, vertically-gradiented panel.

    Frameless top-level widgets render square by default; this + WA_Translucent
    Background is the standard Qt way to get a rounded custom-chrome window.
    """
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()), PANEL_RADIUS, PANEL_RADIUS)
    gradient = QLinearGradient(0, 0, 0, widget.height())
    gradient.setColorAt(0, top)
    gradient.setColorAt(1, bottom)
    painter.fillPath(path, gradient)


def _add_drop_shadow(widget: QWidget):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 140))
    widget.setGraphicsEffect(shadow)


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

    def resume(self):
        self._timer.start(110)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(ACCENT_YELLOW)
        painter.setPen(Qt.NoPen)
        rect = QRectF(2, 2, self._diameter - 4, self._diameter - 4)
        start_angle = int(self._mouth_deg * 16)
        span_angle = int((360 - 2 * self._mouth_deg) * 16)
        painter.drawPie(rect, start_angle, span_angle)


def _pill_button(text: str, bg: str, fg: str = "#FFFFFF") -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg}; color: {fg}; border: none;
            border-radius: 10px; padding: 7px 16px; font-weight: 600;
        }}
        QPushButton:hover {{ background-color: {bg}dd; }}
        QPushButton:pressed {{ background-color: {bg}aa; }}
    """)
    return btn


class TakeNotesPopup(QDialog):
    def __init__(self, platform: str):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 150)
        _add_drop_shadow(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.addWidget(PacmanWidget(34))
        title = QLabel(f"{platform} meeting detected")
        title.setStyleSheet(f"color: {INK_WHITE.name()}; font-size: 14pt; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        subtitle = QLabel("Want me to take notes for this one?")
        subtitle.setStyleSheet(f"color: {INK_WHITE.name()}; font-size: 10.5pt;")
        layout.addWidget(subtitle)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        no_btn = _pill_button("Not now", "#5A4E85")
        yes_btn = _pill_button("Yes, record", "#2ECC71")
        no_btn.clicked.connect(self.reject)
        yes_btn.clicked.connect(self.accept)
        buttons.addWidget(no_btn)
        buttons.addWidget(yes_btn)
        layout.addLayout(buttons)

        self._center_on_screen()

    def paintEvent(self, event):
        _paint_rounded_panel(self, BG_TOP, BG_BOTTOM)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 60)


class FloatingBar(QWidget):
    screenshot_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()

    STATUS_DEFAULT = "Listening for what matters..."

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(360, 64)
        self.setMinimumSize(150, 50)
        _add_drop_shadow(self)

        self._drag_pos = None
        self._is_minimized = False
        self._normal_size = self.size()

        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._status_reset_timer = QTimer(self)
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(lambda: self.status_label.setText(self.STATUS_DEFAULT))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.pacman = PacmanWidget(36)
        layout.addWidget(self.pacman)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        rec_row = QHBoxLayout()
        rec_row.setSpacing(6)
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #FF5C5C; font-size: 9pt;")
        self.timer_label = QLabel("REC 00:00")
        self.timer_label.setStyleSheet(f"color: {INK_WHITE.name()}; font-weight: 700; font-size: 10.5pt;")
        rec_row.addWidget(self.dot)
        rec_row.addWidget(self.timer_label)
        rec_row.addStretch()
        text_col.addLayout(rec_row)
        self.status_label = QLabel(self.STATUS_DEFAULT)
        self.status_label.setStyleSheet("color: #C9BFEE; font-size: 8.5pt;")
        text_col.addWidget(self.status_label)
        layout.addLayout(text_col)
        layout.addStretch()

        self.screenshot_btn = _pill_button("📷", "#5A4E85")
        self.screenshot_btn.setFixedWidth(40)
        self.pause_btn = _pill_button("⏸ Pause", "#E0A030")
        self.stop_btn = _pill_button("⏹ Stop", "#E74C3C")
        self.minimize_btn = _pill_button("—", "#5A4E85")
        self.minimize_btn.setFixedWidth(32)

        self.screenshot_btn.clicked.connect(self._on_screenshot_clicked)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.minimize_btn.clicked.connect(self._toggle_minimize)

        layout.addWidget(self.screenshot_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.stop_btn)
        layout.addWidget(self.minimize_btn)

        # Lets the user resize the window (frameless windows get no native
        # resize handles); pinned to the corner manually in resizeEvent since
        # a linear layout has no "corner" slot to place it in.
        self.size_grip = QSizeGrip(self)
        self.size_grip.setStyleSheet("background: transparent;")

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.right() - self.width() - 20, screen.top() + 20)

    def paintEvent(self, event):
        _paint_rounded_panel(self, BG_TOP, BG_BOTTOM)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.size_grip.move(self.width() - self.size_grip.width(), self.height() - self.size_grip.height())
        self.size_grip.raise_()

    def mousePressEvent(self, event):
        # Only start a drag if the click landed on bare background, not a
        # child widget (buttons/labels need their own clicks to still work).
        if event.button() == Qt.LeftButton and self.childAt(event.position().toPoint()) is None:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _toggle_minimize(self):
        self._is_minimized = not self._is_minimized
        visible = not self._is_minimized
        for widget in (self.pacman, self.dot, self.timer_label, self.status_label, self.screenshot_btn, self.pause_btn, self.stop_btn):
            widget.setVisible(visible)
        self.minimize_btn.setText("▢" if self._is_minimized else "—")
        if self._is_minimized:
            self._normal_size = self.size()
            self.setMinimumSize(70, 40)  # the normal-mode floor would otherwise clamp this resize
            self.resize(70, 40)
        else:
            self.setMinimumSize(150, 50)
            self.resize(self._normal_size)

    def _on_screenshot_clicked(self):
        self.status_label.setText("📸 Got it!")
        self._status_reset_timer.start(2000)
        self.screenshot_clicked.emit()

    def set_paused_visual(self, is_paused: bool):
        if is_paused:
            self._timer.stop()
            self.pacman.stop()
            self.pause_btn.setText("▶ Resume")
            self.dot.setStyleSheet("color: #E0A030; font-size: 9pt;")
            self.status_label.setText("Paused")
        else:
            self._timer.start(1000)
            self.pacman.resume()
            self.pause_btn.setText("⏸ Pause")
            self.dot.setStyleSheet("color: #FF5C5C; font-size: 9pt;")
            self.status_label.setText(self.STATUS_DEFAULT)

    def _tick(self):
        self._elapsed += 1
        minutes, seconds = divmod(self._elapsed, 60)
        self.timer_label.setText(f"REC {minutes:02d}:{seconds:02d}")

    def closeEvent(self, event):
        self._timer.stop()
        self.pacman.stop()
        super().closeEvent(event)


from .settings_dialog import SettingsDialog


class PipelineWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, wav_path: Path, screenshots: list, cfg: dict, platform: str, meeting_title: str | None = None):
        super().__init__()
        self.wav_path = wav_path
        self.screenshots = screenshots
        self.cfg = cfg
        self.platform = platform
        self.meeting_title = meeting_title

    def run(self):
        try:
            result = run_pipeline(self.wav_path, self.screenshots, self.cfg, self.platform, self.meeting_title)
            self.finished_ok.emit(result)
        except PipelineError as e:
            self.failed.emit(str(e))
        except Exception as e:
            self.failed.emit(f"Unexpected error: {e}")


class Controller:
    """Wires detection -> popup -> recording -> floating bar -> pipeline -> tray."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.recorder = Recorder()
        self.detector = MeetingDetector()
        self.detector.meeting_detected.connect(self._on_meeting_detected)
        self.detector.meeting_ended.connect(self._on_meeting_ended)

        self.tray = QSystemTrayIcon(app_icon())
        self.tray.setToolTip("Meeting Agent")
        menu = QMenu()
        menu.addAction("Dashboard", self._open_dashboard)
        menu.addAction("Take notes now", self._on_manual_trigger)
        menu.addAction("Settings", self._open_settings)
        menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self._recording = False
        self._platform = None
        self._session_dir: Path | None = None
        self._meeting_title: str | None = None
        self._paused = False
        self._screenshots: list[Path] = []
        self._floating_bar: FloatingBar | None = None
        self._worker: PipelineWorker | None = None
        self._active_popup: TakeNotesPopup | None = None
        self._dashboard = None

    def start(self):
        self.detector.start()

    def _quit(self):
        self.detector.stop()
        self.detector.wait(2000)
        if self._worker is not None and self._worker.isRunning():
            # Tearing down the app while the pipeline QThread is still alive
            # crashes with "QThread: Destroyed while thread is still running"
            # (reproduced live). Pipeline steps are all network/CPU calls with
            # no natural cancellation point, so wait for it rather than kill it.
            self._worker.wait(30000)
        QApplication.quit()

    def _open_settings(self):
        dialog = SettingsDialog(self.cfg)
        if dialog.exec() == QDialog.Accepted:
            self.cfg = dialog.cfg

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._open_dashboard()

    def _open_dashboard(self):
        if self._dashboard is None:
            from .dashboard import DashboardWindow  # local import: dashboard.py imports from this module
            self._dashboard = DashboardWindow(self)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()

    def _on_manual_trigger(self):
        if self._recording:
            return
        self._begin_capture("Manual")
        self._show_floating_bar()

    def _on_meeting_detected(self, platform: str):
        if self._recording:
            return
        # Capture must not start until the user explicitly consents (Yes). A
        # prior version pre-warmed the audio streams while the popup was still
        # showing to hide stream-connection latency -- that recorded audio
        # before consent and, if the meeting ended before the user answered,
        # could get processed and emailed with no consent ever given. Reverted:
        # the ~1.5-2s stream-connection latency is now eaten after Yes instead.
        popup = TakeNotesPopup(platform)
        self._active_popup = popup
        accepted = popup.exec() == QDialog.Accepted
        self._active_popup = None
        if accepted:
            self._begin_capture(platform)
            self._show_floating_bar()

    def _on_meeting_ended(self):
        if self._active_popup is not None:
            # Meeting vanished while "Take notes?" was still up and unanswered
            # -- close it rather than let a stale popup accept into a dead
            # meeting (or, with pre-warmed capture, process without consent).
            self._active_popup.reject()
            return
        if self._recording:
            self._stop_and_process()

    def _begin_capture(self, platform: str):
        self._recording = True
        self._paused = False
        self._platform = platform
        self._screenshots = []
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self._session_dir = Path(self.cfg["output_dir"]) / f"session-{stamp}"
        self._meeting_title = self._lookup_calendar_title()
        self.recorder.start()

    def _lookup_calendar_title(self) -> str | None:
        # Best-effort: no Google connection yet, API hiccup, or nothing on the
        # calendar right now must never block starting a recording.
        if not google_auth.is_connected():
            return None
        try:
            return calendar_lookup.get_current_event_title()
        except Exception:
            return None

    def _show_floating_bar(self):
        self._floating_bar = FloatingBar()
        self._floating_bar.screenshot_clicked.connect(self._on_screenshot)
        self._floating_bar.stop_clicked.connect(self._stop_and_process)
        self._floating_bar.pause_clicked.connect(self._on_pause_toggle)
        self._floating_bar.show()

    def _on_pause_toggle(self):
        self._paused = not self._paused
        if self._paused:
            self.recorder.pause()
        else:
            self.recorder.resume()
        if self._floating_bar:
            self._floating_bar.set_paused_visual(self._paused)

    def _on_screenshot(self):
        if not self._session_dir:
            return
        try:
            self._screenshots.append(screenshotter.take_screenshot(self._session_dir))
        except Exception as e:
            self.tray.showMessage("Screenshot Failed", str(e), QSystemTrayIcon.Warning)

    def _stop_and_process(self):
        if not self._recording:
            return
        self._recording = False
        self.detector.notify_meeting_ended_externally()

        if self._floating_bar:
            self._floating_bar.close()
            self._floating_bar = None

        try:
            wav_path = self.recorder.stop(self._session_dir / "audio.wav")
        except Exception as e:
            self.tray.showMessage("Meeting Agent Error", f"Recording failed: {e}", QSystemTrayIcon.Warning)
            return

        if self.recorder.loopback_error:
            self.tray.showMessage(
                "Loopback Capture Failed",
                f"Only your microphone was recorded -- other participants' audio "
                f"was missed ({self.recorder.loopback_error}).",
                QSystemTrayIcon.Warning,
            )

        self._worker = PipelineWorker(wav_path, self._screenshots, self.cfg, self._platform, self._meeting_title)
        self._worker.finished_ok.connect(self._on_pipeline_finished)
        self._worker.failed.connect(self._on_pipeline_failed)
        self._worker.start()

    def _on_pipeline_finished(self, result):
        self.tray.showMessage(
            "Meeting Notes Ready",
            f"Saved {result.pdf_path.name} and emailed the link.",
            QSystemTrayIcon.Information,
        )

    def _on_pipeline_failed(self, message: str):
        self.tray.showMessage("Meeting Agent Error", message, QSystemTrayIcon.Warning)
