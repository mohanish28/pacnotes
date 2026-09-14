# Meeting Agent

Windows tray app that detects Zoom / Google Meet / Microsoft Teams calls, records
speaker + mic audio, transcribes locally (faster-whisper), enhances the notes with
Gemini, renders a PDF, uploads it (Cloudflare R2 or Google Drive, your choice), and
emails the recipient a link via the Gmail API. Optionally looks up what's on your
Google Calendar right now to title the recording with the real meeting name.

The user only ever sees a "Take notes?" popup and a small floating control bar.

## Setup

### 1. Gemini API key
Get one from https://aistudio.google.com/apikey.

### 2. Google Cloud OAuth (Gmail send + Calendar lookup + optional Drive storage)
One OAuth grant covers all three. Narrow scopes on purpose (`gmail.send`,
`calendar.readonly`, `drive.file`) — this app never reads your mail or your whole
Drive, only sends and creates the files it uploads itself.

1. https://console.cloud.google.com/ → create a project (or reuse one).
2. Enable these three APIs (each is Library → search → Enable):
   - https://console.cloud.google.com/apis/library/gmail.googleapis.com
   - https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
   - https://console.cloud.google.com/apis/library/drive.googleapis.com
3. **OAuth consent screen** (sidebar): User type **External** → Create. App name
   anything, your email for support/developer contact. On the Scopes step, "Add or
   Remove Scopes" and paste in manually:
   - `https://www.googleapis.com/auth/gmail.send`
   - `https://www.googleapis.com/auth/calendar.readonly`
   - `https://www.googleapis.com/auth/drive.file`

   On the Test users step, add your own Google account. Leaving the app in
   **Testing** status (not "Published") means Google never requires the full
   sensitive-scope verification review — that's only for apps other people install.
4. **Credentials** (sidebar) → Create Credentials → OAuth client ID → Application
   type **Desktop app** → Create → **Download JSON**.
5. Save that downloaded file as `google_credentials.json` in the same folder as
   `config.json` (see below for the path; on Linux that's `~/.meeting_agent/`).
6. In the app's Settings dialog, click **Connect Google Account** — opens a browser
   for the one-time consent, then stores a refreshable token next to the config.

### 3. Storage: Cloudflare R2 or Google Drive
Pick one in Settings (`storage_backend`). Google Drive needs nothing beyond the
OAuth connection above. For Cloudflare R2:
1. Cloudflare dashboard → R2 → create a bucket.
2. R2 → Manage API Tokens → create a token with read/write access to that bucket.
3. Note down: **Account ID**, **Access Key ID**, **Secret Access Key**, and the
   **bucket name** — fill those four into Settings.

Either way, the app uploads the PDF (and, if "keep audio" is on, the WAV) and
emails a link that expires after 7 days — no public bucket access needed.

### 4. Install dependencies
```
pip install -r requirements.txt
```

### 5. Run
```
python -m meeting_agent
```
On first run it opens a Settings dialog since the config is empty. Fill in the
Gemini key and recipient email, click **Connect Google Account**, pick a storage
backend (and fill its R2 fields if you chose R2), then Save. After that it lives
in the system tray.

Config is stored at `%APPDATA%\MeetingAgent\config.json` (Windows) or
`~/.meeting_agent/config.json` (Linux/Mac) — `google_credentials.json` and the
OAuth token live in that same folder.

## Adding to Windows startup

**Option A — Startup folder:**
1. Press `Win+R`, run `shell:startup`.
2. Create a shortcut there pointing to `pythonw.exe -m meeting_agent` (use `pythonw`
   so no console window appears), with "Start in" set to the project folder.

**Option B — Task Scheduler:**
1. Open Task Scheduler → Create Task.
2. Trigger: "At log on".
3. Action: start a program → `pythonw.exe`, arguments `-m meeting_agent`, start in
   the project folder.
4. Check "Run whether user is logged on or not" if desired.

## Building a single .exe (PyInstaller)
```
pip install pyinstaller
pyinstaller --noconsole --onefile --name MeetingAgent --add-data "meeting-notes-prompt.md;." -m meeting_agent
```
The `--add-data` flag ships `meeting-notes-prompt.md` alongside the exe — the app
looks for it next to the package, so keep it in the same folder as the built exe.

## Running on Linux

Everything works on Linux except automatic meeting detection has one caveat:
detection is X11-based (via `python-xlib`), so it sees X11 and XWayland-mapped
windows but not native-Wayland app windows. On a plain GNOME/Wayland session
with native-Wayland Zoom/Chrome, auto-popup may never fire — use **Take notes
now** in the tray menu instead, which skips detection entirely and works
identically everywhere. On X11 sessions (Xorg login, XFCE, KDE X11, i3, sway
with XWayland, etc.) auto-detection works normally.

`pip install -r requirements.txt` picks the right window-detection dependency
per OS automatically (`pygetwindow` on Windows, `python-xlib` on Linux).

**Browsers on Wayland**: some browsers (confirmed: Google Chrome and Zen on
Ubuntu 26.04/GNOME) render natively on Wayland by default, which makes them
completely invisible to X11-based detection — not a title-matching issue,
the browser produces zero X11 windows at all. If Google Meet/Teams in your
browser never triggers the popup, force that browser to use XWayland:
- **Chrome**: launch with `google-chrome --ozone-platform=x11`, or make it
  permanent by copying `/usr/share/applications/google-chrome.desktop` to
  `~/.local/share/applications/google-chrome.desktop` and adding
  `--ozone-platform=x11` to each `Exec=` line (fully quit Chrome first —
  it's single-instance, so a running process ignores new launch flags).
- **Firefox-based browsers** (Zen, Firefox): set `MOZ_ENABLE_WAYLAND=0`
  before launching.

Screenshots (the floating bar's 📷 button) have the same root cause on
Wayland: `mss` reads pixels via X11, which the compositor doesn't expose.
Fixed via the XDG Desktop Portal Screenshot API instead (see
`screenshotter.py`) — no user setup needed, this one just works.

### Linux autostart + desktop launcher
```
./scripts/setup_autostart_linux.sh
```
Installs a `.desktop` entry so Meeting Agent shows up in your app grid/search
for manual launching, and a copy in `~/.config/autostart/` so it starts
automatically on login. Re-run it any time after moving the checkout or
rebuilding `.venv`. Requires `.venv` to already exist (see step 4 above).

### Linux `meeting-agent` command
```
./scripts/install_cli_linux.sh
```
Installs `meeting-agent` to `~/.local/bin`, so you can just type `meeting-agent`
from any directory/terminal to launch it (no `cd`, no venv activation). If
config is incomplete it opens the Settings dialog same as any other launch.

## Dashboard
Tray menu → **Dashboard**: lists past meetings (Open PDF / Copy Link / Delete),
a **New meeting now** button (same manual-trigger path as the tray menu item),
and a **Settings** button.

## Notes
- CUDA is used for transcription automatically if available, otherwise it falls
  back to CPU (`transcriber.py`).
- `whisper_model` in config can be `tiny`, `base`, `small`, `medium`, `large-v3`, etc.
- Capture, transcription, Gemini, storage upload, and email failures never crash
  the app — they show up as a tray notification.
- Calendar title lookup is best-effort: if nothing's on your calendar right now,
  or Google isn't connected, recordings just fall back to the platform name
  (Zoom/Google Meet/Microsoft Teams/Manual).
