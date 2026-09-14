"""On-demand full-screen screenshots, saved next to the meeting's audio/PDF.

Windows and macOS use mss (reads the framebuffer directly via GDI / Quartz --
works fine on both; macOS may prompt for Screen Recording permission the
first time, under System Settings -> Privacy & Security). Linux under Wayland
cannot: mss reads pixels via X11 APIs, which the Wayland compositor never
exposes to arbitrary clients (a deliberate security boundary, confirmed here
by mss silently "succeeding" with a solid-black image). The correct Linux
path is the XDG Desktop Portal's Screenshot API, which asks the compositor
itself to grab the frame and hands back a file. Uses jeepney (pure Python, no
system D-Bus bindings needed) instead of shelling out to `gdbus`, whose
piped-monitor output proved unreliable for catching the async Response.
"""
import shutil
import sys
import time
from pathlib import Path


def _take_screenshot_mss(output_dir: Path) -> Path:
    import mss

    filename = output_dir / f"screenshot_{int(time.time() * 1000)}.png"
    with mss.mss() as sct:
        sct.shot(mon=0, output=str(filename))
    return filename


def _take_screenshot_linux(output_dir: Path) -> Path:
    from jeepney import DBusAddress, MatchRule, new_method_call
    from jeepney.io.blocking import open_dbus_connection

    portal = DBusAddress(
        object_path="/org/freedesktop/portal/desktop",
        bus_name="org.freedesktop.portal.Desktop",
        interface="org.freedesktop.portal.Screenshot",
    )
    conn = open_dbus_connection(bus="SESSION")
    try:
        msg = new_method_call(portal, "Screenshot", "sa{sv}", ("", {"interactive": ("b", False)}))
        reply = conn.send_and_get_reply(msg)
        request_path = reply.body[0]

        rule = MatchRule(
            type="signal", interface="org.freedesktop.portal.Request",
            member="Response", path=request_path,
        )
        with conn.filter(rule) as queue:
            response = conn.recv_until_filtered(queue, timeout=10)
    finally:
        conn.close()

    code, results = response.body
    if code != 0:
        raise RuntimeError(f"Screenshot portal request failed or was denied (response code {code}).")

    uri = results["uri"][1]
    src = Path(uri.removeprefix("file://"))
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"screenshot_{int(time.time() * 1000)}.png"
    shutil.move(str(src), str(dest))
    return dest


def take_screenshot(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform in ("win32", "darwin"):
        return _take_screenshot_mss(output_dir)
    return _take_screenshot_linux(output_dir)
