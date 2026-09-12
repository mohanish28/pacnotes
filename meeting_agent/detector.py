"""Polls window titles to detect the start/end of a Zoom / Meet / Teams call."""
from PySide6.QtCore import QThread, Signal
import pygetwindow as gw

POLL_INTERVAL_SEC = 2.0
CONFIRM_POLLS = 2  # consecutive matching polls required before firing an event


def _current_meeting_platform() -> str | None:
    for window in gw.getAllWindows():
        title = window.title
        if not title:
            continue
        if title == "Zoom Meeting":
            return "Zoom"
        if "Meet -" in title:
            return "Google Meet"
        if "Microsoft Teams" in title and "Meeting" in title:
            return "Microsoft Teams"
    return None


class MeetingDetector(QThread):
    """Background thread emitting meeting_detected(platform) / meeting_ended()."""

    meeting_detected = Signal(str)
    meeting_ended = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._active = False
        self._pending_platform = None
        self._pending_count = 0
        self._absent_count = 0

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            try:
                platform = _current_meeting_platform()
            except Exception:
                platform = None  # window enumeration can fail transiently

            if self._active:
                if platform is None:
                    self._absent_count += 1
                    if self._absent_count >= CONFIRM_POLLS:
                        self._active = False
                        self._absent_count = 0
                        self.meeting_ended.emit()
                else:
                    self._absent_count = 0
            else:
                if platform is not None and platform == self._pending_platform:
                    self._pending_count += 1
                else:
                    self._pending_platform = platform
                    self._pending_count = 1 if platform is not None else 0

                if platform is not None and self._pending_count >= CONFIRM_POLLS:
                    self._active = True
                    self._pending_count = 0
                    self._pending_platform = None
                    self.meeting_detected.emit(platform)

            self.msleep(int(POLL_INTERVAL_SEC * 1000))

    def notify_meeting_ended_externally(self):
        """Reset active state when the user manually stops a meeting."""
        self._active = False
        self._absent_count = 0
