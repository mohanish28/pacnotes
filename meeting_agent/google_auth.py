"""One Google OAuth grant shared by Gmail send, Drive upload, and Calendar lookup.

Narrow scopes on purpose: gmail.send (not full mail access), drive.file (only
files this app creates, not the whole Drive), calendar.readonly (never needs
to write events). Keeping the app in Google's "Testing" publishing status
with just the owner as a test user means these scopes never trigger Google's
sensitive-scope verification review -- that review is for apps other people
install, not a personal tool.
"""
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
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def disconnect() -> None:
    _token_path().unlink(missing_ok=True)
