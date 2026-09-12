"""Emails the recipient a link to the uploaded meeting notes PDF via SMTP.

Generic SMTP (STARTTLS) rather than Gmail-specific -- works with Brevo, SES,
or any other SMTP relay by pointing smtp_host/port/login/password at it.
"""
import smtplib
from email.mime.text import MIMEText


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
    msg["From"] = cfg["sender_email"]
    msg["To"] = cfg["recipient_email"]

    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
        server.starttls()
        server.login(cfg["smtp_login"], cfg["smtp_password"])
        server.sendmail(cfg["sender_email"], [cfg["recipient_email"]], msg.as_string())
