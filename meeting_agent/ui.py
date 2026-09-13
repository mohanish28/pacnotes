"""All PySide6 UI: tray icon, popup, floating control bar, settings dialog, controller."""
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, Signal, QThread
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFormLayout, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import config as config_module
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

    STATUS_DEFAULT = "Listening for what matters..."

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 64)
        _add_drop_shadow(self)

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
        dot = QLabel("●")
        dot.setStyleSheet("color: #FF5C5C; font-size: 9pt;")
        self.timer_label = QLabel("REC 00:00")
        self.timer_label.setStyleSheet(f"color: {INK_WHITE.name()}; font-weight: 700; font-size: 10.5pt;")
        rec_row.addWidget(dot)
        rec_row.addWidget(self.timer_label)
        rec_row.addStretch()
        text_col.addLayout(rec_row)
        self.status_label = QLabel(self.STATUS_DEFAULT)
        self.status_label.setStyleSheet("color: #C9BFEE; font-size: 8.5pt;")
        text_col.addWidget(self.status_label)
        layout.addLayout(text_col)
        layout.addStretch()

        screenshot_btn = _pill_button("📷", "#5A4E85")
        screenshot_btn.setFixedWidth(40)
        stop_btn = _pill_button("⏹ Stop", "#E74C3C")

        screenshot_btn.clicked.connect(self._on_screenshot_clicked)
        stop_btn.clicked.connect(self.stop_clicked.emit)

        layout.addWidget(screenshot_btn)
        layout.addWidget(stop_btn)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.right() - self.width() - 20, screen.top() + 20)

    def paintEvent(self, event):
        _paint_rounded_panel(self, BG_TOP, BG_BOTTOM)

    def _on_screenshot_clicked(self):
        self.status_label.setText("📸 Got it!")
        self._status_reset_timer.start(2000)
        self.screenshot_clicked.emit()

    def _tick(self):
        self._elapsed += 1
        minutes, seconds = divmod(self._elapsed, 60)
        self.timer_label.setText(f"REC {minutes:02d}:{seconds:02d}")

    def closeEvent(self, event):
        self._timer.stop()
        self.pacman.stop()
        super().closeEvent(event)


SECRET_FIELDS = {"gemini_api_key", "smtp_password", "r2_secret_access_key"}
BOOL_FIELDS = {"auto_email", "keep_audio"}


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict):
        super().__init__()
        self.setWindowTitle("Meeting Agent Settings")
        self.cfg = dict(cfg)
        self._inputs = {}

        layout = QFormLayout(self)
        for field, default in config_module.DEFAULTS.items():
            if field in BOOL_FIELDS:
                widget = QCheckBox()
                widget.setChecked(bool(self.cfg.get(field, default)))
            else:
                widget = QLineEdit(str(self.cfg.get(field, default)))
                if field in SECRET_FIELDS:
                    widget.setEchoMode(QLineEdit.Password)
            self._inputs[field] = widget
            layout.addRow(field.replace("_", " ").title(), widget)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        layout.addRow(save_btn)

    def _save(self):
        for field, widget in self._inputs.items():
            if field in BOOL_FIELDS:
                self.cfg[field] = widget.isChecked()
            else:
                self.cfg[field] = widget.text().strip()

        if not config_module.is_config_complete(self.cfg):
            missing = [f for f in config_module.REQUIRED_FIELDS if not self.cfg.get(f)]
            QMessageBox.warning(self, "Incomplete settings", f"Missing: {', '.join(missing)}")
            return

        config_module.save_config(self.cfg)
        self.accept()


class PipelineWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, wav_path: Path, screenshots: list, cfg: dict, platform: str):
        super().__init__()
        self.wav_path = wav_path
        self.screenshots = screenshots
        self.cfg = cfg
        self.platform = platform

    def run(self):
        try:
            result = run_pipeline(self.wav_path, self.screenshots, self.cfg, self.platform)
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
        menu.addAction("Take notes now", self._on_manual_trigger)
        menu.addAction("Settings", self._open_settings)
        menu.addAction("Quit", self._quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

        self._recording = False
        self._platform = None
        self._session_dir: Path | None = None
        self._screenshots: list[Path] = []
        self._floating_bar: FloatingBar | None = None
        self._worker: PipelineWorker | None = None
        self._active_popup: TakeNotesPopup | None = None

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
        self._platform = platform
        self._screenshots = []
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self._session_dir = Path(self.cfg["output_dir"]) / f"session-{stamp}"
        self.recorder.start()

    def _show_floating_bar(self):
        self._floating_bar = FloatingBar()
        self._floating_bar.screenshot_clicked.connect(self._on_screenshot)
        self._floating_bar.stop_clicked.connect(self._stop_and_process)
        self._floating_bar.show()

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

        self._worker = PipelineWorker(wav_path, self._screenshots, self.cfg, self._platform)
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
