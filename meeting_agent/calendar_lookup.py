"""Looks up the calendar event happening right now, to give a recording a real
title ("Weekly Sync with Design Team") instead of just the platform name.

Best-effort by design: called at the moment recording starts, and a failure
here (no Calendar access yet, API hiccup, nothing on the calendar) must never
block or fail an actual recording -- callers should catch and ignore errors.
"""
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from . import google_auth

# Wide enough to still find a long meeting whose start drifted from "now",
# narrow enough that Calendar doesn't hand back the whole day's agenda.
LOOKUP_WINDOW = timedelta(hours=3)


def get_current_event_title() -> str | None:
    creds = google_auth.get_credentials()
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    events = service.events().list(
        calendarId="primary",
        timeMin=(now - LOOKUP_WINDOW).isoformat(),
        timeMax=(now + LOOKUP_WINDOW).isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    for event in events.get("items", []):
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue  # all-day event (date, not dateTime) -- not "happening now"
        if datetime.fromisoformat(start) <= now <= datetime.fromisoformat(end):
            return event.get("summary")
    return None
