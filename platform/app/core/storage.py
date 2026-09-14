"""Object storage.

Audio never passes through the API. The browser asks for a presigned URL, PUTs
the bytes straight to Cloudflare R2, and the worker GETs them the same way. The
API only ever moves the key around, which is what keeps a free-tier dyno viable.

Without R2 credentials this falls back to disk so the stack runs end-to-end on
a laptop with no cloud account.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class PresignedUpload:
    url: str
    method: str
    key: str
    headers: dict[str, str]
    expires_in: int
    backend: str


def build_key(user_id: str, filename: str, prefix: str = "recordings") -> str:
    """Keys are date-partitioned so a bucket listing stays browsable."""
    stamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    suffix = Path(filename).suffix or ".webm"
    return f"{prefix}/{user_id}/{stamp}/{uuid.uuid4().hex}{suffix}"


class _R2Backend:
    name = "r2"

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4", region_name="auto"),
        )

    def presign_put(self, key: str, content_type: str) -> PresignedUpload:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.r2_bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=settings.presign_ttl_seconds,
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            key=key,
            headers={"Content-Type": content_type},
            expires_in=settings.presign_ttl_seconds,
            backend=self.name,
        )

    def presign_get(self, key: str) -> str:
        if settings.r2_public_base_url:
            return f"{settings.r2_public_base_url.rstrip('/')}/{key}"
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_bucket, "Key": key},
            ExpiresIn=settings.presign_ttl_seconds,
        )

    def head(self, key: str) -> dict | None:
        try:
            return self._client.head_object(Bucket=settings.r2_bucket, Key=key)
        except Exception:
            return None


class _LocalBackend:
    """Dev-only. The API accepts the PUT itself and writes to disk."""

    name = "local"

    def __init__(self) -> None:
        self.root = Path(settings.local_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        log.warning("storage: R2 not configured, writing uploads to %s", self.root)

    def path_for(self, key: str) -> Path:
        # Refuse anything that would escape the storage root.
        target = (self.root / key).resolve()
        if not str(target).startswith(str(self.root)):
            raise ValueError("Rejected a storage key that escapes the storage root.")
        return target

    def presign_put(self, key: str, content_type: str) -> PresignedUpload:
        return PresignedUpload(
            url=f"/v1/storage/local/{key}",
            method="PUT",
            key=key,
            headers={"Content-Type": content_type},
            expires_in=settings.presign_ttl_seconds,
            backend=self.name,
        )

    def presign_get(self, key: str) -> str:
        return f"/v1/storage/local/{key}"

    def head(self, key: str) -> dict | None:
        p = self.path_for(key)
        if not p.exists():
            return None
        return {"ContentLength": p.stat().st_size}

    def write(self, key: str, body: bytes) -> int:
        p = self.path_for(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return len(body)

    def read(self, key: str) -> bytes | None:
        p = self.path_for(key)
        return p.read_bytes() if p.exists() else None


_backend: _R2Backend | _LocalBackend | None = None


def backend() -> _R2Backend | _LocalBackend:
    global _backend
    if _backend is None:
        _backend = _R2Backend() if settings.storage_configured else _LocalBackend()
    return _backend


def presign_put(key: str, content_type: str) -> PresignedUpload:
    return backend().presign_put(key, content_type)


def presign_get(key: str) -> str:
    return backend().presign_get(key)
