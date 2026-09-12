"""Emails the recipient a link to the uploaded meeting notes PDF via Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_notification_email(cfg: dict, platform: str, pdf_url: str, audio_url: str | None) -> None:
    lines = [
        f"Your meeting notes from the {platform} call are ready.",
        "",
        f"Notes PDF: {pdf_url}",
    ]
    if audio_url:
        lines.append(f"Audio recording: {audio_url}")
    lines.append("")
    lines.append(f"(Links expire in 7 days.)")

    msg = MIMEText("\n".join(lines))
    msg["Subject"] = f"Meeting Notes - {platform}"
    msg["From"] = cfg["gmail_address"]
    msg["To"] = cfg["recipient_email"]

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(cfg["gmail_address"], cfg["gmail_app_password"])
        server.sendmail(cfg["gmail_address"], [cfg["recipient_email"]], msg.as_string())
