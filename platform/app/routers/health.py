"""Health endpoints.

`/health` is the liveness probe Render pings — cheap, no dependencies.
`/health/ready` is the one a human reads: it names every dependency and whether
it is actually wired up, which turns "why doesn't sign-in work" into a
five-second check instead of a debugging session.
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from app.config import settings
from app.core import db, queue

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.env}


@router.get("/health/coach")
async def coach_probe() -> dict:
    """Can this key actually reach the coach model?

    `coach: ok` in /health/ready only means the key is non-empty, which stayed
    true through a malformed key and again through a project with no access to
    gpt-4o-mini. One retrieve call answers it for real, and needs no sign-in, so
    a deploy can be checked from outside.
    """
    from app.services.coach import CoachUnavailable, _client, _explain

    if not settings.coach_configured:
        return {"ok": False, "model": settings.coach_model, "error": "OPENAI_API_KEY is not set"}
    try:
        await _client().models.retrieve(settings.coach_model)
    except Exception as exc:  # every failure here is a configuration answer
        err = _explain(exc) if not isinstance(exc, CoachUnavailable) else exc
        return {"ok": False, "model": settings.coach_model, "error": str(err)}
    return {"ok": True, "model": settings.coach_model}


@router.get("/health/ready")
async def ready() -> dict:
    mongo_ok = await db.ping()
    redis_ok = await queue.ping()
    checks = {
        "mongo": {"ok": mongo_ok, "required": True},
        "redis": {"ok": redis_ok, "required": False, "note": "falls back to Mongo polling"},
        "google_auth": {"ok": settings.google_configured, "required": True},
        "storage": {
            "ok": settings.storage_configured,
            "required": False,
            "backend": "r2" if settings.storage_configured else "local-disk",
        },
        "coach": {"ok": settings.coach_configured, "required": False},
    }
    degraded = [name for name, c in checks.items() if not c["ok"]]
    required_down = [name for name, c in checks.items() if c["required"] and not c["ok"]]
    worker: dict = {"enabled": settings.embedded_worker}
    if settings.embedded_worker:
        from app.worker_runner import STATUS

        worker.update(STATUS)
        beat = STATUS.get("heartbeat") or {}
        last = beat.get("last_tick")
        worker["seconds_since_tick"] = round(time.time() - last, 1) if last else None
        worker["jobs_done"] = beat.get("jobs_done")
        worker["last_job_error"] = beat.get("last_error")
        # A loop that hasn't ticked in a minute is wedged, whatever it claims.
        worker["alive"] = last is not None and (time.time() - last) < 60

    return {
        "status": "down" if required_down else ("degraded" if degraded else "ok"),
        "checks": checks,
        "queue_depth": await queue.depth(),
        "worker": worker,
    }
