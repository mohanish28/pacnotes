"""One Google OAuth grant shared by Gmail send, Drive upload, and Calendar lookup.

Narrow scopes on purpose: gmail.send (not full mail access), drive.file (only
files this app creates, not the whole Drive), calendar.readonly (never needs
to write events). Keeping the app in Google's "Testing" publishing status
with just the owner as a test user means these scopes never trigger Google's
sensitive-scope verification review -- that review is for apps other people
install, not a personal tool.
"""
import contextlib
import json
import os
import shutil
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .config import _config_dir

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _client_secret_path() -> Path:
    return _config_dir() / "google_credentials.json"


def _token_path() -> Path:
    return _config_dir() / "google_token.json"


def is_connected() -> bool:
    return _token_path().exists()


def has_client_secret() -> bool:
    return _client_secret_path().exists()


def install_client_secret(src_path: Path) -> None:
    """Copy a downloaded OAuth client JSON into place, after a basic shape check.

    Raises ValueError if the file doesn't look like a Google "Desktop app"
    client secret, so a wrong file picked in the setup dialog fails with a
    clear message instead of a cryptic error during the browser flow later.
    """
    try:
        data = json.loads(Path(src_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Couldn't read that file as JSON: {e}") from e

    if "installed" not in data and "web" not in data:
        raise ValueError(
            "That doesn't look like a Google OAuth client file. In Google Cloud "
            "Console, create an OAuth client of type \"Desktop app\" and download "
            "its JSON."
        )

    dest = _client_secret_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_path, dest)


@contextlib.contextmanager
def _real_ld_library_path():
    """Undo the PyInstaller onefile bootloader's LD_LIBRARY_PATH override.

    The bootloader points LD_LIBRARY_PATH at its own bundled libs so the
    frozen app's imports resolve -- but a subprocess it spawns (here, the
    browser that run_local_server() opens via webbrowser.open()) inherits
    that same override and can fail to launch against incompatible bundled
    libs. Reproduced live: Connect Account froze indefinitely on the
    packaged Linux build with no browser ever opening. PyInstaller saves
    the pre-override value in *_ORIG specifically for this case.
    """
    if not getattr(sys, "frozen", False):
        yield
        return
    saved = os.environ.get("LD_LIBRARY_PATH")
    orig = os.environ.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        os.environ["LD_LIBRARY_PATH"] = orig
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ["LD_LIBRARY_PATH"] = saved
        else:
            os.environ.pop("LD_LIBRARY_PATH", None)


def get_credentials() -> Credentials:
    """Valid credentials for the shared scopes, refreshing or re-consenting as needed.

    Raises FileNotFoundError if google_credentials.json (the OAuth client
    downloaded from Cloud Console) hasn't been placed yet -- there is nothing
    to start a consent flow with otherwise.
    """
    token_path = _token_path()
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    client_secret = _client_secret_path()
    if not client_secret.exists():
        msg = (
            f"No Google OAuth client found at {client_secret}. Download it from "
            "Google Cloud Console (Credentials -> your Desktop OAuth client -> "
            "Download JSON) and save it there."
        )
        raise FileNotFoundError(msg)

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    with _real_ld_library_path():
        creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def disconnect() -> None:
    _token_path().unlink(missing_ok=True)
