"""Worker-side object storage reads. Mirrors the API's backend selection."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from config import settings

log = logging.getLogger(__name__)


def _r2_client():
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4", region_name="auto"),
    )


def download(key: str) -> Path:
    """Fetch an object to a temp file. Caller deletes it."""
    suffix = Path(key).suffix or ".webm"
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    handle.close()
    target = Path(handle.name)

    if settings.storage_configured:
        _r2_client().download_file(settings.r2_bucket, key, str(target))
        return target

    source = (Path(settings.local_storage_dir).resolve() / key).resolve()
    root = Path(settings.local_storage_dir).resolve()
    if not str(source).startswith(str(root)):
        raise ValueError("Rejected a storage key that escapes the storage root.")
    if not source.exists():
        raise FileNotFoundError(f"No object at {key}")
    target.write_bytes(source.read_bytes())
    return target
