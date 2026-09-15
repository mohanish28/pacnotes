#!/bin/bash
# Creates a desktop launcher (app grid / manual start) and an autostart entry
# (runs on login) for Meeting Agent, pointing at this checkout's .venv.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "No .venv found at $PROJECT_DIR/.venv -- run this first:" >&2
    echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

mkdir -p ~/.local/share/applications ~/.config/autostart

# Filename (pacnotes.desktop) must match app.setDesktopFileName("pacnotes") in
# main.py -- that's how GNOME's dock/Alt-Tab resolve the real Name/Icon below
# instead of falling back to the raw process name when launched from a terminal.
DESKTOP_ENTRY=$(cat << EOF
[Desktop Entry]
Type=Application
Name=PacNotes
Comment=Automatic meeting note-taker (Zoom/Meet/Teams -> transcript -> notes -> email)
Exec="$VENV_PYTHON" -m meeting_agent
Path=$PROJECT_DIR
Icon=$PROJECT_DIR/meeting_agent/assets/icon.png
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
)

echo "$DESKTOP_ENTRY" > ~/.local/share/applications/pacnotes.desktop
echo "$DESKTOP_ENTRY" > ~/.config/autostart/pacnotes.desktop
rm -f ~/.local/share/applications/meeting-agent.desktop ~/.config/autostart/meeting-agent.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true

echo "Installed:"
echo "  ~/.local/share/applications/pacnotes.desktop (search/app grid launch)"
echo "  ~/.config/autostart/pacnotes.desktop (runs automatically on login)"
