"""All PySide6 UI: tray icon, popup, floating control bar, settings dialog, controller."""
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QStyle, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from . import config as config_module
from . import screenshotter
from .detector import MeetingDetector
from .pipeline import PipelineError, run_pipeline
from .recorder import Recorder


def _app_icon() -> QIcon:
    # No shipped asset -> reuse a built-in Qt icon rather than adding an image file.
    return QApplication.style().standardIcon(QStyle.SP_ComputerIcon)


class TakeNotesPopup(QDialog):
    def __init__(self, platform: str):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(300, 120)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{platform} meeting detected.\nTake notes?"))

        buttons = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        no_btn = QPushButton("No")
        yes_btn.clicked.connect(self.accept)
        no_btn.clicked.connect(self.reject)
        buttons.addWidget(yes_btn)
        buttons.addWidget(no_btn)
        layout.addLayout(buttons)

        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 60)


class FloatingBar(QWidget):
    screenshot_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFixedSize(260, 50)

        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        layout = QHBoxLayout(self)
        self.timer_label = QLabel("REC 00:00")
        screenshot_btn = QPushButton("📷 Screenshot")
        stop_btn = QPushButton("⏹ Stop & Send")

        screenshot_btn.clicked.connect(self.screenshot_clicked.emit)
        stop_btn.clicked.connect(self.stop_clicked.emit)

        layout.addWidget(self.timer_label)
        layout.addWidget(screenshot_btn)
        layout.addWidget(stop_btn)

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.right() - self.width() - 20, screen.top() + 20)

    def _tick(self):
        self._elapsed += 1
        minutes, seconds = divmod(self._elapsed, 60)
        self.timer_label.setText(f"REC {minutes:02d}:{seconds:02d}")

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


SECRET_FIELDS = {"gemini_api_key", "gmail_app_password", "r2_secret_access_key"}
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

        self.tray = QSystemTrayIcon(_app_icon())
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
        if self._session_dir:
            self._screenshots.append(screenshotter.take_screenshot(self._session_dir))

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
