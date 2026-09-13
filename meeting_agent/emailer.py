"""Emails the recipient a link to the uploaded meeting notes PDF via SMTP.

Generic SMTP (STARTTLS) rather than Gmail-specific -- works with Brevo, SES,
or any other SMTP relay by pointing smtp_host/port/login/password at it.
"""
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid


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
    # RFC 5322 requires Date and treats Message-ID as standard practice; Python's
    # email lib adds neither automatically. Confirmed live via SMTP debug trace
    # that our raw DATA payload had no Date header at all -- a well-known signal
    # strict receivers (Gmail included) use to silently drop an otherwise-valid,
    # relay-accepted message with no bounce.
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=cfg["sender_email"].split("@")[-1])

    with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
        server.starttls()
        server.login(cfg["smtp_login"], cfg["smtp_password"])
        server.sendmail(cfg["sender_email"], [cfg["recipient_email"]], msg.as_string())
