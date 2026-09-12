# Meeting Agent

Windows tray app that detects Zoom / Google Meet / Microsoft Teams calls, records
speaker + mic audio, transcribes locally (faster-whisper), enhances the notes with
Gemini, renders a PDF, uploads it to Cloudflare R2, and emails the recipient a link.

The user only ever sees a "Take notes?" popup and a small floating control bar.

## Setup

### 1. Gemini API key
Get one from https://aistudio.google.com/apikey.

### 2. SMTP relay (Brevo, or any other provider)
Email delivery is generic SMTP (STARTTLS), so any relay works. For Brevo:
1. Brevo dashboard → SMTP & API → SMTP tab, to get your SMTP credentials.
2. Fill in Settings: `smtp_host` = `smtp-relay.brevo.com`, `smtp_port` = `587`,
   `smtp_login` = the generated login (looks like `xxxxx@smtp-brevo.com`),
   `smtp_password` = the SMTP key, `sender_email` = an address verified as a
   sender in your Brevo account (this is the "From" address, separate from the
   login).

### 3. Cloudflare R2 (PDF/audio delivery)
1. In the Cloudflare dashboard, go to R2 → create a bucket.
2. R2 → Manage API Tokens → create a token with read/write access to that bucket.
3. Note down: **Account ID**, **Access Key ID**, **Secret Access Key**, and the
   **bucket name**. The app uploads the PDF (and, if "keep audio" is on, the WAV)
   and emails a link that expires after 7 days — no public bucket access needed.

### 4. Install dependencies
```
pip install -r requirements.txt
```

### 5. Run
```
python -m meeting_agent
```
On first run it opens a Settings dialog since the config is empty. Fill in the
Gemini key, Gmail address + app password, recipient email, and the four R2 fields,
then Save. After that it lives in the system tray.

Config is stored at `%APPDATA%\MeetingAgent\config.json`.

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

## Notes
- CUDA is used for transcription automatically if available, otherwise it falls
  back to CPU (`transcriber.py`).
- `whisper_model` in config can be `tiny`, `base`, `small`, `medium`, `large-v3`, etc.
- Capture, transcription, Gemini, R2, and email failures never crash the app — they
  show up as a tray notification.
