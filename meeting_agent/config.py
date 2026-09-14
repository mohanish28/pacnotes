"""Config loading/saving for the meeting agent.

Stored as JSON in %APPDATA%\\MeetingAgent\\config.json on Windows (falls back to
~/.meeting_agent on other platforms, for local development).
"""
import json
import os
from pathlib import Path

DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-3.6-flash",
    "recipient_email": "",
    "whisper_model": "small",
    "output_dir": str(Path.home() / "MeetingNotes"),
    "auto_email": True,
    "keep_audio": False,
    "storage_backend": "r2",  # "r2" or "drive" -- drive just needs the shared Google OAuth below
    "r2_account_id": "",
    "r2_access_key_id": "",
    "r2_secret_access_key": "",
    "r2_bucket_name": "",
}

# Text fields that are always required, regardless of storage_backend.
BASE_REQUIRED_FIELDS = ["gemini_api_key", "recipient_email"]

# Only required when storage_backend == "r2"; Drive needs no extra fields,
# just the Google OAuth connection every backend already needs for Gmail send.
R2_REQUIRED_FIELDS = ["r2_account_id", "r2_access_key_id", "r2_secret_access_key", "r2_bucket_name"]


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".meeting_agent"
    return base / "MeetingAgent" if appdata else base


def _config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict:
    """Load config from disk, filling in any missing keys with defaults."""
    cfg = dict(DEFAULTS)
    path = _config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt config -> fall back to defaults, user re-fills settings
    return cfg


def save_config(cfg: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def missing_fields(cfg: dict) -> list[str]:
    """Text config fields still empty, given the current storage_backend choice."""
    required = list(BASE_REQUIRED_FIELDS)
    if cfg.get("storage_backend") == "r2":
        required += R2_REQUIRED_FIELDS
    return [f for f in required if not cfg.get(f)]


def is_config_complete(cfg: dict) -> bool:
    from . import google_auth  # local import: google_auth imports _config_dir from this module

    return not missing_fields(cfg) and google_auth.is_connected()
