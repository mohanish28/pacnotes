# Meeting Agent

Windows tray app that detects Zoom / Google Meet / Microsoft Teams calls, records
speaker + mic audio, transcribes locally (faster-whisper), enhances the notes with
Gemini, renders a PDF, uploads it to Cloudflare R2, and emails the recipient a link.

The user only ever sees a "Take notes?" popup and a small floating control bar.

## Setup

### 1. Gemini API key
Get one from https://aistudio.google.com/apikey.

### 2. Gmail App Password
Regular Gmail passwords don't work with SMTP. Create an App Password:
1. Enable 2-Step Verification on the Google account: https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Create an app password for "Mail" and copy the 16-character code.

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

## Notes
- CUDA is used for transcription automatically if available, otherwise it falls
  back to CPU (`transcriber.py`).
- `whisper_model` in config can be `tiny`, `base`, `small`, `medium`, `large-v3`, etc.
- Capture, transcription, Gemini, R2, and email failures never crash the app — they
  show up as a tray notification.
