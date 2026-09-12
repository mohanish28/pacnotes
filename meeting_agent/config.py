"""Config loading/saving for the meeting agent.

Stored as JSON in %APPDATA%\\MeetingAgent\\config.json on Windows (falls back to
~/.meeting_agent on other platforms, for local development).
"""
import json
import os
from pathlib import Path

DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "gmail_address": "",
    "gmail_app_password": "",
    "recipient_email": "",
    "whisper_model": "small",
    "output_dir": str(Path.home() / "MeetingNotes"),
    "auto_email": True,
    "keep_audio": False,
    "r2_account_id": "",
    "r2_access_key_id": "",
    "r2_secret_access_key": "",
    "r2_bucket_name": "",
}

# Fields that must be non-empty before the pipeline can run end to end.
REQUIRED_FIELDS = [
    "gemini_api_key",
    "gmail_address",
    "gmail_app_password",
    "recipient_email",
    "r2_account_id",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_bucket_name",
]


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


def is_config_complete(cfg: dict) -> bool:
    return all(cfg.get(field) for field in REQUIRED_FIELDS)
