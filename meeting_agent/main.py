"""App entry point: loads config, ensures it's complete, starts the tray controller."""
import sys

from PySide6.QtWidgets import QApplication, QDialog

from . import config as config_module
from .icons import app_icon
from .ui import Controller, SettingsDialog


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setApplicationName("PacNotes")
    # Must match the installed .desktop file's id (pacnotes.desktop) so GNOME's
    # dock/Alt-Tab show the real name+icon instead of falling back to the raw
    # process name ("python3") when launched from a terminal, not the launcher.
    app.setDesktopFileName("pacnotes")

    cfg = config_module.load_config()
    if not config_module.is_config_complete(cfg):
        dialog = SettingsDialog(cfg)
        if dialog.exec() != QDialog.Accepted:
            sys.exit(0)
        cfg = dialog.cfg

    controller = Controller(cfg)
    controller.start()

    if "--dashboard" in sys.argv or "-d" in sys.argv:
        controller._open_dashboard()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
