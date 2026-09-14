"""Emails the recipient a link to the uploaded meeting notes PDF via the Gmail API.

Replaces the earlier generic-SMTP approach: sending as a gmail.com address
through any third-party relay (Brevo included) gets silently dropped by
Gmail's own anti-spoofing, since only Google can DKIM-sign for gmail.com
(confirmed live -- Brevo's own error: "sender ... is not valid ... authenticate
your domain"). The Gmail API sends through Google's own infrastructure as the
OAuth-authenticated user, which is the one path where that's a non-issue.
"""
import base64
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from googleapiclient.discovery import build

from . import google_auth


def send_notification_email(cfg: dict, platform: str, pdf_url: str, audio_url: str | None) -> None:
    lines = [
        f"Your meeting notes from the {platform} call are ready.",
        "",
        f"Notes PDF: {pdf_url}",
    ]
    if audio_url:
        lines.append(f"Audio recording: {audio_url}")
    lines.append("")
    lines.append("(Links expire in 7 days.)")

    msg = MIMEText("\n".join(lines))
    msg["Subject"] = f"Meeting Notes - {platform}"
    msg["To"] = cfg["recipient_email"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")

    creds = google_auth.get_credentials()
    service = build("gmail", "v1", credentials=creds)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
