"""Uploads a file to Google Drive and returns a link-viewable share link.

Alternative to storage.py's Cloudflare R2 upload -- same call shape
(upload_and_get_link(path, cfg) -> url) so pipeline.py can pick either
backend without branching on anything but which function to call.
"""
import mimetypes
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import google_auth


def upload_and_get_link(file_path: Path, cfg: dict) -> str:
    creds = google_auth.get_credentials()
    service = build("drive", "v3", credentials=creds)

    mimetype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    media = MediaFileUpload(str(file_path), mimetype=mimetype)
    file = service.files().create(body={"name": file_path.name}, media_body=media, fields="id").execute()
    file_id = file["id"]

    # drive.file scope only grants access to files this app itself created,
    # so it can still manage sharing on files it just uploaded like this one.
    service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    result = service.files().get(fileId=file_id, fields="webViewLink").execute()
    return result["webViewLink"]
