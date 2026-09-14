"""Polls window titles to detect the start/end of a Zoom / Meet / Teams call.

Windows uses pygetwindow. Linux has no pygetwindow support at all (it raises
NotImplementedError on import), so it enumerates X11 windows directly via Xlib
instead — this only sees X11 and XWayland-mapped windows. On a pure-Wayland
session with no X11 windows (e.g. stock GNOME Wayland with native-Wayland apps),
title enumeration returns nothing and auto-detection silently never fires; the
tray's "Take notes now" still works manually. macOS uses Quartz's window list
API directly (pyobjc) -- unverified against a real call, no Mac available to
test on; written against Apple's documented CGWindowListCopyWindowInfo behavior.
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
    if title == "Meeting" and wm_class and "zoom" in wm_class:
        # Verified on a real Zoom Linux build: the in-call window's actual title
        # is bare "Meeting" (the lobby window is "Zoom Workplace - ..."), not
        # "Zoom Meeting" as older docs/spec assume. wm_class (Linux WM_CLASS, or
        # the owning app's name on macOS -- e.g. "zoom.us") is required since
        # "Meeting" alone is too generic (e.g. a calendar event window).
        return "Zoom"
    if title.startswith("Meet -"):
        # Verified live: an active call's tab title is "Meet - xxx-yyyy-zzz -
        # Google Chrome" (starts with "Meet -"). The pre-join lobby page's tab
        # is "Google Meet - Google Chrome" -- a plain `"Meet -" in title` check
        # false-positives on it too, since that substring appears later in the
        # lobby's title as well. startswith() distinguishes an actual call.
        return "Google Meet"
    if "Microsoft Teams" in title and "Meeting" in title:
        return "Microsoft Teams"
    return None


def _all_window_titles_windows() -> list[tuple[str, str | None]]:
    import pygetwindow as gw

    return [(w.title, None) for w in gw.getAllWindows()]


def _all_window_titles_macos() -> list[tuple[str, str | None]]:
    # CGWindowListCopyWindowInfo is the standard macOS API for this (what
    # window-listing utilities generally use) -- no Accessibility permission
    # needed for the window list itself, but kCGWindowName can come back empty
    # for other apps' windows until the user grants this app Screen Recording
    # access under System Settings -> Privacy & Security (macOS 10.15+).
    # UNVERIFIED: written against Quartz's documented behavior, no Mac to test
    # detection against a real Zoom/Meet/Teams call.
    import Quartz

    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    entries = []
    for window in window_list:
        title = window.get("kCGWindowName") or ""
        owner = window.get("kCGWindowOwnerName") or ""
        if title:
            entries.append((title, owner.lower() or None))
    return entries


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
    if sys.platform == "win32":
        entries = _all_window_titles_windows()
    elif sys.platform == "darwin":
        entries = _all_window_titles_macos()
    else:
        entries = _all_window_titles_linux()
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

            # Sleep in small chunks rather than one 2000ms msleep so stop()
            # takes effect within ~100ms instead of up to a full poll interval.
            # Reproduced live: Controller._quit()'s detector.wait(2000) raced
            # against this exact sleep duration and lost, tearing the app down
            # while the thread was still alive ("QThread: Destroyed while
            # thread is still running", Aborted/core dumped).
            slept = 0
            while slept < POLL_INTERVAL_SEC * 1000 and self._running:
                self.msleep(100)
                slept += 100

    def notify_meeting_ended_externally(self):
        """Reset active state when the user manually stops a meeting."""
        self._active = False
        self._absent_count = 0
