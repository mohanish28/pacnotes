"""Polls window titles to detect the start/end of a Zoom / Meet / Teams call.

Windows uses pygetwindow. Linux has no pygetwindow support at all (it raises
NotImplementedError on import), so it enumerates X11 windows directly via Xlib
instead — this only sees X11 and XWayland-mapped windows. On a pure-Wayland
session with no X11 windows (e.g. stock GNOME Wayland with native-Wayland apps),
title enumeration returns nothing and auto-detection silently never fires; the
tray's "Take notes now" still works manually.
"""
import sys

from PySide6.QtCore import QThread, Signal

POLL_INTERVAL_SEC = 2.0
CONFIRM_POLLS = 2  # consecutive matching polls required before firing an event


def _classify_title(title: str, wm_class: str | None = None) -> str | None:
    if not title:
        return None
    if title == "Zoom Meeting":
        return "Zoom"
    if title == "Meeting" and wm_class == "zoom":
        # Verified on a real Zoom Linux build: the in-call window's actual title
        # is bare "Meeting" (the lobby window is "Zoom Workplace - ..."), not
        # "Zoom Meeting" as older docs/spec assume. WM_CLASS is required here
        # since "Meeting" alone is too generic (e.g. a calendar event window).
        return "Zoom"
    if "Meet -" in title:
        return "Google Meet"
    if "Microsoft Teams" in title and "Meeting" in title:
        return "Microsoft Teams"
    return None


def _all_window_titles_windows() -> list[tuple[str, str | None]]:
    import pygetwindow as gw

    return [(w.title, None) for w in gw.getAllWindows()]


_x11_display = None
_x11_unsupported = False


def _all_window_titles_linux() -> list[tuple[str, str | None]]:
    # ponytail: X11/XWayland only, no wlr-foreign-toplevel or GNOME "Window Calls"
    # support; add one of those if native-Wayland detection is ever needed.
    global _x11_display, _x11_unsupported
    if _x11_unsupported:
        return []
    try:
        from Xlib import display
        from Xlib.error import XError

        if _x11_display is None:
            _x11_display = display.Display()
        root = _x11_display.screen().root
        net_client_list = _x11_display.intern_atom("_NET_CLIENT_LIST")
        net_wm_name = _x11_display.intern_atom("_NET_WM_NAME")
        client_list = root.get_full_property(net_client_list, 0)
        if client_list is None:
            return []

        entries = []
        for window_id in client_list.value:
            try:
                window = _x11_display.create_resource_object("window", window_id)
                name_prop = window.get_full_property(net_wm_name, 0)
                wm_class = window.get_wm_class()
            except XError:
                continue
            if name_prop and name_prop.value:
                value = name_prop.value
                title = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
                entries.append((title, wm_class[1].lower() if wm_class else None))
        return entries
    except Exception:
        # No X11 display (e.g. python-xlib missing, or a pure-Wayland session
        # with no XWayland root) -> detection degrades to manual trigger only.
        _x11_unsupported = True
        return []


def _current_meeting_platform() -> str | None:
    entries = _all_window_titles_windows() if sys.platform == "win32" else _all_window_titles_linux()
    for title, wm_class in entries:
        platform = _classify_title(title, wm_class)
        if platform:
            return platform
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
