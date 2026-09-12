# **Role:**
You are a senior Python desktop-app engineer. You build a complete, runnable Windows tray application from this spec, with clean modules and no placeholders.

# **Objective:**
Build an automatic meeting note-taker for Windows. A background agent detects when a Zoom / Google Meet / Microsoft Teams call starts, pops up "Take notes?", and on Yes records the call, lets the user grab screenshots, then — on meeting end or Stop — transcribes locally, enhances the notes with the Gemini API, renders a PDF, and emails it. The user only ever sees a popup and a small floating control bar.

# **Context:**
- Target machine: Windows (Dell G15 with an NVIDIA GPU — use CUDA for transcription when available, else CPU).
- The AI cannot listen to a live call directly; audio must be captured from the system. Capturing the **speaker loopback** (what the user hears) is mandatory — mic-only recording misses everyone else. Mix loopback + mic into one 16 kHz mono WAV.
- Notes are enhanced by Gemini using the separate meeting-notes prompt file (`meeting-notes-prompt.md`) as the system instruction. Do not rewrite that prompt; load it from disk.
- Email goes through Gmail SMTP and requires a Google **App Password**, not the account login password.
- Config is stored as JSON in `%APPDATA%\MeetingAgent\config.json`: gemini_api_key, gemini_model, gmail_address, gmail_app_password, recipient_email, whisper_model, output_dir, auto_email, keep_audio.

# **Instructions:**

## **Instruction 1 — Stack and structure:**
Use Python with: PySide6 (popup, tray, floating bar), soundcard (loopback + mic capture), numpy (mixing), mss (screenshots), faster-whisper (local transcription), google-genai (`from google import genai`; `client.models.generate_content(model="gemini-2.5-flash", contents=..., config=types.GenerateContentConfig(system_instruction=...))`), markdown + xhtml2pdf + Pillow (PDF with embedded screenshots), smtplib (email), psutil + pygetwindow (meeting detection). Split into modules: config, detector, recorder, screenshotter, transcriber, enhancer, pdf_report, emailer, pipeline, ui, main. Provide requirements.txt and a README.

## **Instruction 2 — Detection and flow:**
Run a background detector thread that polls window titles: Zoom = a window titled "Zoom Meeting"; Google Meet = a browser title containing "Meet -"; Teams = title with "Microsoft Teams" + "Meeting". Require the meeting to be seen on two consecutive polls before firing, to avoid false triggers. On detection, show a frameless always-on-top "Take notes?" popup. On Yes: start recording and show a small always-on-top bar with a REC timer, a "📷 Screenshot" button, and a "⏹ Stop & Send" button. Auto-stop and process when the meeting window disappears, or when Stop is clicked.

## **Instruction 3 — Pipeline and delivery:**
On stop, run this in a worker thread so the UI never freezes: save the mixed WAV → transcribe with faster-whisper (timestamped text) → send the transcript to Gemini with the prompt file as system instruction → get Markdown notes → render a styled PDF (embed any screenshots as an appendix) → email the PDF via Gmail SMTP to the recipient → show a tray notification. On first run, if config is incomplete, open a settings dialog. Sit in the system tray with menu items: Take notes now, Settings, Quit.

# **Notes:**
- Never leave TODOs or stub functions — every module must be fully implemented and importable.
- Wrap capture, transcription, API, and email steps in try/except and surface errors as tray notifications, not crashes.
- Do not commit secrets; read the Gemini key and Gmail app password from the config file only.
- Include README steps for: getting a Gemini API key, creating a Gmail App Password, `pip install -r requirements.txt`, running with `python -m meeting_agent`, and adding it to Windows startup (Startup folder or Task Scheduler) plus building a single .exe with PyInstaller.
- Keep the user-facing surface minimal: only the popup and the floating bar should ever appear during a meeting.
