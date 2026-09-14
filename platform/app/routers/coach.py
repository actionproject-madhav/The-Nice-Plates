"""Coach endpoints.

Threads are stored so a conversation survives a page reload, and so we have a
transcript to put in the demo — the proposal promises "sample query
transcripts", and this is where they come from.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.deps import Db, UserId
from app.routers.pieces import oid, serialize
from app.schemas import CoachRequest, CoachResponse
from app.services import coach as coach_service
from nplates_data.collections import Collections
from nplates_data.models import utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/coach", tags=["coach"])

MAX_TURNS_SENT = 20


@router.post("/ask", response_model=CoachResponse)
async def ask(body: CoachRequest, db: Db, user_id: UserId) -> CoachResponse:
    threads = db[Collections.COACH_THREADS]

    if body.thread_id:
        thread = await threads.find_one({"_id": oid(body.thread_id), "user_id": user_id})
        if thread is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that conversation.")
    else:
        result = await threads.insert_one(
            {
                "user_id": user_id,
                "piece_id": body.piece_id,
                "title": body.message[:60],
                "messages": [],
                "created_at": utcnow(),
                "updated_at": utcnow(),
            }
        )
        thread = await threads.find_one({"_id": result.inserted_id})

    # Only the plain text turns go back to the model; tool blocks are replayed
    # within a single call, not across them.
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in thread.get("messages", [])[-MAX_TURNS_SENT:]
    ]

    try:
        reply, tools_used = await coach_service.ask(db, user_id, history, body.message)
    except coach_service.CoachUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The coach isn't configured yet — the API is missing its OpenAI key.",
        ) from exc
    except Exception as exc:
        log.exception("coach turn failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The coach couldn't answer just now. Try again."
        ) from exc

    await db[Collections.COACH_THREADS].update_one(
        {"_id": thread["_id"]},
        {
            "$push": {
                "messages": {
                    "$each": [
                        {"role": "user", "content": body.message, "at": utcnow()},
                        {
                            "role": "assistant",
                            "content": reply,
                            "at": utcnow(),
                            "tools_used": tools_used,
                        },
                    ]
                }
            },
            "$set": {"updated_at": utcnow()},
        },
    )

    from app.config import settings

    return CoachResponse(
        thread_id=str(thread["_id"]),
        reply=reply,
        tools_used=tools_used,
        model=settings.coach_model,
    )


@router.get("/threads")
async def list_threads(db: Db, user_id: UserId, limit: int = 20) -> list[dict]:
    cursor = (
        db[Collections.COACH_THREADS]
        .find({"user_id": user_id}, {"messages": {"$slice": -2}})
        .sort("updated_at", -1)
        .limit(min(limit, 50))
    )
    return [serialize(d) async for d in cursor]


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, db: Db, user_id: UserId) -> dict:
    doc = await db[Collections.COACH_THREADS].find_one(
        {"_id": oid(thread_id), "user_id": user_id}
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We couldn't find that conversation.")
    return serialize(doc)
