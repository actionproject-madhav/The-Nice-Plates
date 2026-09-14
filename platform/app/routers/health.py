"""Health endpoints.

`/health` is the liveness probe Render pings — cheap, no dependencies.
`/health/ready` is the one a human reads: it names every dependency and whether
it is actually wired up, which turns "why doesn't sign-in work" into a
five-second check instead of a debugging session.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.core import db, queue

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.env}


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
    return {
        "status": "down" if required_down else ("degraded" if degraded else "ok"),
        "checks": checks,
        "queue_depth": await queue.depth(),
        "embedded_worker": settings.embedded_worker,
    }
