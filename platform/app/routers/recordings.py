"""Recordings: presign, register, enqueue, poll.

The three-step upload is the important shape here:

  1. POST /recordings/upload-url  → a recording row + a presigned PUT
  2. the browser PUTs bytes straight to R2 (never through this API)
  3. POST /recordings/{id}/complete → marks it uploaded and queues analysis

Step 2 bypassing the API is what lets a free 512MB instance accept a 40MB
take without falling over.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core import queue, storage
from app.deps import Db, UserId
from app.routers.pieces import oid, serialize
from app.schemas import RecordingStatus, UploadComplete, UploadRequest, UploadTicket
from nplates_data.collections import Collections
from nplates_data.models import AnalysisJob, Feedback, JobStatus, Recording, utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/recordings", tags=["recordings"])

ALLOWED_AUDIO = {
    "audio/webm",
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
}
MAX_UPLOAD_BYTES = 64 * 1024 * 1024


@router.post("/upload-url", response_model=UploadTicket)
async def create_upload_url(body: UploadRequest, db: Db, user_id: UserId) -> UploadTicket:
    if body.content_type not in ALLOWED_AUDIO:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"We can't read {body.content_type}. Try WebM, WAV, MP3 or FLAC.",
        )

    key = storage.build_key(user_id, body.filename)
    recording = Recording(
        user_id=user_id,
        session_id=body.session_id,
        piece_id=body.piece_id,
        section_id=body.section_id,
        storage_key=key,
        content_type=body.content_type,
        status="pending",
    )
    result = await db[Collections.RECORDINGS].insert_one(recording.to_mongo())
    ticket = storage.presign_put(key, body.content_type)

    return UploadTicket(
        recording_id=str(result.inserted_id),
        key=key,
        upload_url=ticket.url,
        method=ticket.method,
        headers=ticket.headers,
        expires_in=ticket.expires_in,
        backend=ticket.backend,
    )


@router.post("/{recording_id}/complete")
async def complete_upload(
    recording_id: str, body: UploadComplete, db: Db, user_id: UserId
) -> dict:
    doc = await db[Collections.RECORDINGS].find_one(
        {"_id": oid(recording_id), "user_id": user_id}
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that recording.")

    if body.size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "That take is too long.")

    # Trust but verify: the browser claims it uploaded, so check the object
    # actually landed before we spend worker time on it.
    head = storage.backend().head(doc["storage_key"])
    if head is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That upload didn't finish. Try recording the take again.",
        )

    job = AnalysisJob(user_id=user_id, recording_id=recording_id, status=JobStatus.QUEUED)
    job_result = await db[Collections.JOBS].insert_one(job.to_mongo())
    job_id = str(job_result.inserted_id)

    await db[Collections.RECORDINGS].update_one(
        {"_id": oid(recording_id)},
        {
            "$set": {
                "status": "uploaded",
                "size_bytes": body.size_bytes or int(head.get("ContentLength", 0)),
                "duration_seconds": body.duration_seconds,
                "job_id": job_id,
                "updated_at": utcnow(),
            }
        },
    )

    if doc.get("session_id"):
        await db[Collections.SESSIONS].update_one(
            {"_id": oid(doc["session_id"])},
            {"$addToSet": {"recording_ids": recording_id}},
        )

    queued = await queue.enqueue({"job_id": job_id, "recording_id": recording_id})
    return {
        "recording_id": recording_id,
        "job_id": job_id,
        "status": "uploaded",
        "queued_via": "redis" if queued else "mongo-poll",
    }


@router.get("/{recording_id}", response_model=RecordingStatus)
async def recording_status(recording_id: str, db: Db, user_id: UserId) -> RecordingStatus:
    doc = await db[Collections.RECORDINGS].find_one(
        {"_id": oid(recording_id), "user_id": user_id}
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that recording.")

    job = None
    if doc.get("job_id"):
        job = await db[Collections.JOBS].find_one({"_id": oid(doc["job_id"])})

    feedback = None
    fb_doc = await db[Collections.FEEDBACK].find_one({"recording_id": recording_id})
    if fb_doc:
        feedback = Feedback.model_validate(fb_doc)

    return RecordingStatus(
        recording_id=recording_id,
        status=doc.get("status", "pending"),
        job_status=(job or {}).get("status"),
        feedback=feedback,
        playback_url=storage.presign_get(doc["storage_key"]),
        error=(job or {}).get("error"),
    )


@router.get("")
async def list_recordings(db: Db, user_id: UserId, limit: int = 25) -> list[dict]:
    cursor = (
        db[Collections.RECORDINGS]
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(min(limit, 100))
    )
    return [serialize(d) async for d in cursor]


# ── Local storage shim (development only) ──────────────────────────────────

local_router = APIRouter(prefix="/storage/local", tags=["storage"], include_in_schema=False)


@local_router.put("/{key:path}")
async def local_put(key: str, request: Request) -> dict:
    from app.config import settings

    if settings.storage_configured:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Too large.")
    size = storage.backend().write(key, body)
    return {"key": key, "size_bytes": size}


@local_router.get("/{key:path}")
async def local_get(key: str) -> Response:
    from app.config import settings

    if settings.storage_configured:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    body = storage.backend().read(key)
    if body is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return Response(content=body, media_type="application/octet-stream")
