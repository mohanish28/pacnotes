"""Uploads a file to Cloudflare R2 (S3-compatible) and returns a time-limited link."""
from pathlib import Path

import boto3

LINK_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days


def _client(cfg: dict):
    endpoint_url = f"https://{cfg['r2_account_id']}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=cfg["r2_access_key_id"],
        aws_secret_access_key=cfg["r2_secret_access_key"],
        region_name="auto",
    )


def upload_and_get_link(file_path: Path, cfg: dict) -> str:
    client = _client(cfg)
    key = f"meeting-notes/{file_path.name}"
    client.upload_file(str(file_path), cfg["r2_bucket_name"], key)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["r2_bucket_name"], "Key": key},
        ExpiresIn=LINK_EXPIRY_SECONDS,
    )
