"""Practice sessions: the timer around a practice run."""

from __future__ import annotations

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from app.deps import Db, UserId
from app.routers.pieces import oid, serialize
from app.schemas import SessionEnd, SessionStart
from nplates_data.collections import Collections
from nplates_data.models import PracticeSession, utcnow

router = APIRouter(prefix="/sessions", tags=["practice"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_session(body: SessionStart, db: Db, user_id: UserId) -> dict:
    session = PracticeSession(user_id=user_id, **body.model_dump())
    result = await db[Collections.SESSIONS].insert_one(session.to_mongo())
    return serialize(await db[Collections.SESSIONS].find_one({"_id": result.inserted_id}))


@router.get("")
async def list_sessions(db: Db, user_id: UserId, limit: int = 50) -> list[dict]:
    cursor = (
        db[Collections.SESSIONS]
        .find({"user_id": user_id})
        .sort("started_at", -1)
        .limit(min(limit, 200))
    )
    return [serialize(d) async for d in cursor]


@router.post("/{session_id}/end")
async def end_session(session_id: str, body: SessionEnd, db: Db, user_id: UserId) -> dict:
    existing = await db[Collections.SESSIONS].find_one(
        {"_id": oid(session_id), "user_id": user_id}
    )
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that session.")
    if existing.get("ended_at"):
        raise HTTPException(status.HTTP_409_CONFLICT, "That session is already finished.")

    await db[Collections.SESSIONS].update_one(
        {"_id": oid(session_id)},
        {
            "$set": {
                "ended_at": utcnow(),
                "duration_seconds": body.duration_seconds,
                "notes": body.notes,
                "updated_at": utcnow(),
            }
        },
    )
    return serialize(await db[Collections.SESSIONS].find_one({"_id": oid(session_id)}))
