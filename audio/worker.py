"""The analysis worker.

Run standalone:   python audio/worker.py
Or in-process:    EMBEDDED_WORKER=true on the API (the default, for free-tier
                  Render, which has no background worker type).

The loop has two ways to find work, which is the whole reliability story:
  * Redis BLPOP — the fast path, sub-second pickup;
  * a periodic Mongo sweep — the backstop, so a dropped Redis message delays a
    job by up to 30 seconds instead of losing it forever.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Make `nplates_data` importable when run directly from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import redis.asyncio as aioredis
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from config import settings
from pipeline.align import compare
from pipeline.score import score
from pipeline.transcribe import transcribe
from nplates_data.collections import Collections
from nplates_data.models import JobStatus, NoteEvent, utcnow

logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)-7s worker: %(message)s"
)
log = logging.getLogger("worker")

_mongo: AsyncIOMotorClient | None = None
_redis: aioredis.Redis | None = None
_last_sweep = 0.0


async def _db():
    global _mongo
    if _mongo is None:
        _mongo = AsyncIOMotorClient(
            settings.mongodb_uri, serverSelectionTimeoutMS=5_000, maxPoolSize=5, tz_aware=True
        )
    return _mongo[settings.mongodb_db]


async def _queue() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            _redis = client
        except Exception as exc:
            log.warning("redis unavailable (%s); running on the Mongo sweep alone", exc)
            return None
    return _redis


async def process_job(db, job_id: str) -> None:
    job = await db[Collections.JOBS].find_one({"_id": ObjectId(job_id)})
    if job is None:
        log.warning("job %s vanished", job_id)
        return
    if job["status"] not in (JobStatus.QUEUED.value, JobStatus.FAILED.value):
        return  # someone else has it

    # Claim it. The status guard in the filter is what stops the embedded
    # worker and a standalone worker from both picking up the same job.
    claimed = await db[Collections.JOBS].find_one_and_update(
        {"_id": ObjectId(job_id), "status": job["status"]},
        {
            "$set": {"status": JobStatus.RUNNING.value, "started_at": utcnow()},
            "$inc": {"attempts": 1},
        },
    )
    if claimed is None:
        return

    recording_id = job["recording_id"]
    audio_path: Path | None = None
    try:
        recording = await db[Collections.RECORDINGS].find_one({"_id": ObjectId(recording_id)})
        if recording is None:
            raise FileNotFoundError(f"recording {recording_id} is gone")

        await db[Collections.RECORDINGS].update_one(
            {"_id": ObjectId(recording_id)}, {"$set": {"status": "analyzing"}}
        )

        import storage_client

        audio_path = storage_client.download(recording["storage_key"])
        log.info("job %s: transcribing %s", job_id, recording["storage_key"])

        result = await asyncio.to_thread(transcribe, str(audio_path))

        # What *should* have been played. Falls back to the performance itself
        # when a piece has no reference transcription, which scores timing and
        # tempo honestly and pitch trivially — better than refusing to analyse.
        expected: list[NoteEvent] = []
        first_bar = 1
        if recording.get("piece_id"):
            piece = await db[Collections.PIECES].find_one(
                {"_id": ObjectId(recording["piece_id"])}
            )
            if piece:
                expected = [NoteEvent.model_validate(n) for n in piece.get("reference_notes", [])]
        if recording.get("section_id"):
            section = await db[Collections.SECTIONS].find_one(
                {"_id": ObjectId(recording["section_id"])}
            )
            if section:
                first_bar = section.get("start_bar", 1)
        if not expected:
            expected = result.notes

        comparisons = await asyncio.to_thread(compare, expected, result.notes)
        feedback = score(
            user_id=job["user_id"],
            recording_id=recording_id,
            comparisons=comparisons,
            played=result.notes,
            expected=expected,
            piece_id=recording.get("piece_id"),
            section_id=recording.get("section_id"),
            first_bar=first_bar,
            engine=result.engine,
            engine_version=result.engine_version,
        )

        # Upsert so a retry replaces the old verdict instead of duplicating it
        # (feedback.recording_id is a unique index).
        await db[Collections.FEEDBACK].update_one(
            {"recording_id": recording_id},
            {"$set": feedback.to_mongo()},
            upsert=True,
        )
        stored = await db[Collections.FEEDBACK].find_one({"recording_id": recording_id})
        feedback_id = str(stored["_id"])

        await db[Collections.JOBS].update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    "status": JobStatus.DONE.value,
                    "finished_at": utcnow(),
                    "feedback_id": feedback_id,
                    "error": None,
                }
            },
        )
        await db[Collections.RECORDINGS].update_one(
            {"_id": ObjectId(recording_id)},
            {
                "$set": {
                    "status": "analyzed",
                    "feedback_id": feedback_id,
                    "duration_seconds": recording.get("duration_seconds")
                    or result.duration_seconds,
                    "updated_at": utcnow(),
                }
            },
        )
        log.info(
            "job %s done via %s: pitch %.0f%%, timing %.0f%%",
            job_id,
            result.engine,
            feedback.pitch_accuracy * 100,
            feedback.timing_accuracy * 100,
        )

    except Exception as exc:
        log.exception("job %s failed", job_id)
        attempts = (claimed.get("attempts", 0) or 0) + 1
        exhausted = attempts >= settings.max_attempts
        await db[Collections.JOBS].update_one(
            {"_id": ObjectId(job_id)},
            {
                "$set": {
                    # Leave it QUEUED while retries remain; the sweep picks it up.
                    "status": JobStatus.FAILED.value if exhausted else JobStatus.QUEUED.value,
                    "error": str(exc)[:500],
                    "finished_at": utcnow() if exhausted else None,
                }
            },
        )
        if exhausted:
            await db[Collections.RECORDINGS].update_one(
                {"_id": ObjectId(recording_id)}, {"$set": {"status": "failed"}}
            )
    finally:
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)


async def sweep(db) -> int:
    """Re-run anything left QUEUED, whatever Redis thinks."""
    stale = (
        await db[Collections.JOBS]
        .find({"status": JobStatus.QUEUED.value, "attempts": {"$lt": settings.max_attempts}})
        .sort("created_at", 1)
        .to_list(length=10)
    )
    for job in stale:
        await process_job(db, str(job["_id"]))
    return len(stale)


async def worker_loop() -> None:
    """One pass: take a Redis message if there is one, sweep on a timer."""
    global _last_sweep
    db = await _db()
    queue = await _queue()

    while True:
        picked = False
        if queue is not None:
            try:
                message = await queue.brpop(settings.analysis_queue, timeout=settings.block_seconds)
                if message:
                    _, raw = message
                    payload = json.loads(raw)
                    await process_job(db, payload["job_id"])
                    picked = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("redis pop failed (%s); relying on the sweep", exc)
                await asyncio.sleep(2)
        else:
            await asyncio.sleep(settings.block_seconds)

        now = time.monotonic()
        if not picked and now - _last_sweep > settings.sweep_every_seconds:
            _last_sweep = now
            found = await sweep(db)
            if found:
                log.info("sweep picked up %d job(s) Redis didn't deliver", found)


async def main() -> None:
    log.info("starting; queue=%s db=%s", settings.analysis_queue, settings.mongodb_db)
    await worker_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("stopped")
