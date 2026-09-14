"""Dashboard window: recent meetings list, manual trigger, settings -- normal QMainWindow chrome
(unlike the frameless popup/floating bar, this one gets native window decorations).
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from . import meetings
from .icons import BG_TOP, app_icon
from .ui import SettingsDialog, _pill_button


def _format_created_at(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S").strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return iso  # unexpected format -> show raw rather than crash the dashboard


class DashboardWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Meeting Agent Dashboard")
        self.setWindowIcon(app_icon())
        self.resize(640, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        new_btn = _pill_button("New meeting now", BG_TOP.name())
        new_btn.clicked.connect(self._on_new_meeting)
        settings_btn = _pill_button("Settings", "#5A4E85")
        settings_btn.clicked.connect(self._on_settings)
        top_bar.addWidget(new_btn)
        top_bar.addWidget(settings_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        layout.addWidget(QLabel("<b>Recent Meetings</b>"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        for record in meetings.list_meetings():
            item = QListWidgetItem()
            row = self._build_row(record)
            item.setSizeHint(row.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row)

    def _build_row(self, record: dict) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)

        label = QLabel(f"{record['platform']} -- {_format_created_at(record['created_at'])}")
        row_layout.addWidget(label)
        row_layout.addStretch()

        open_btn = QPushButton("Open PDF")
        open_btn.clicked.connect(lambda: self._open_pdf(record["pdf_path"]))
        row_layout.addWidget(open_btn)

        copy_btn = QPushButton("Copy Link")
        copy_btn.setToolTip(record.get("pdf_url") or "")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(record.get("pdf_url") or ""))
        row_layout.addWidget(copy_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self._on_delete(record["id"]))
        row_layout.addWidget(delete_btn)

        return row

    def _open_pdf(self, pdf_path: str):
        path = Path(pdf_path)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, "File not found", f"PDF not found on disk:\n{pdf_path}")

    def _on_delete(self, meeting_id: str):
        reply = QMessageBox.question(
            self, "Delete meeting",
            "Delete this meeting and its PDF? This cannot be undone.",
        )
        if reply == QMessageBox.Yes:
            meetings.delete_meeting(meeting_id)
            self.refresh()

    def _on_new_meeting(self):
        self.controller._on_manual_trigger()

    def _on_settings(self):
        dialog = SettingsDialog(self.controller.cfg)
        if dialog.exec() == QDialog.Accepted:
            self.controller.cfg = dialog.cfg
