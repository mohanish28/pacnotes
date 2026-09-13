"""Registry of past meetings (for the dashboard's Recent Meetings list).

Stored as JSON next to config.json, since nothing else here needs a real
database yet -- one small list of records, read/written wholesale.
"""
import json
import time
import uuid
from pathlib import Path

from .config import _config_dir


def _registry_path() -> Path:
    return _config_dir() / "meetings.json"


def list_meetings() -> list[dict]:
    """All recorded meetings, newest first."""
    path = _registry_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []  # corrupt registry -> treat as empty rather than crash the dashboard
    return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)


def _save(records: list[dict]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def add_meeting(platform: str, pdf_path: Path, pdf_url: str, audio_url: str | None = None) -> dict:
    record = {
        "id": uuid.uuid4().hex,
        "platform": platform,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pdf_path": str(pdf_path),
        "pdf_url": pdf_url,
        "audio_url": audio_url,
    }
    records = list_meetings()
    records.append(record)
    _save(records)
    return record


def delete_meeting(meeting_id: str, delete_pdf_file: bool = True) -> None:
    records = list_meetings()
    target = next((r for r in records if r["id"] == meeting_id), None)
    if target is None:
        return
    if delete_pdf_file:
        try:
            Path(target["pdf_path"]).unlink(missing_ok=True)
        except OSError:
            pass  # file already gone or inaccessible -> registry entry still removed below
    remaining = [r for r in records if r["id"] != meeting_id]
    _save(remaining)
