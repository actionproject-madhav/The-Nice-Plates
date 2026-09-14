"""The progress dashboard.

Everything here is one aggregation pipeline per question, run against the
`user_recent` indexes. Deliberately no per-session round trips — the dashboard
is the page people open most and it should cost two queries, not two hundred.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.deps import Db, UserId
from app.schemas import DaySummary, ProgressSummary
from nplates_data.collections import Collections

router = APIRouter(prefix="/progress", tags=["progress"])


def _streaks(days: set[str]) -> tuple[int, int]:
    """Current and longest run of consecutive practice days."""
    if not days:
        return 0, 0

    parsed = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in days)

    longest = run = 1
    for prev, cur in zip(parsed, parsed[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)

    # The current streak only counts if it reaches today or yesterday —
    # practising last Tuesday isn't a streak.
    today = datetime.now(timezone.utc).date()
    current = 0
    if parsed[-1] in (today, today - timedelta(days=1)):
        current = 1
        for prev, cur in zip(reversed(parsed[:-1]), reversed(parsed[1:])):
            if (cur - prev).days == 1:
                current += 1
            else:
                break
    return current, longest


@router.get("/summary", response_model=ProgressSummary)
async def summary(db: Db, user_id: UserId, days: int = 30) -> ProgressSummary:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    per_day = await db[Collections.SESSIONS].aggregate(
        [
            {"$match": {"user_id": user_id, "started_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$started_at"}},
                    "seconds": {"$sum": "$duration_seconds"},
                    "sessions": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    ).to_list(length=days + 1)

    totals = await db[Collections.SESSIONS].aggregate(
        [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "seconds": {"$sum": "$duration_seconds"},
                    "sessions": {"$sum": 1},
                    "pieces": {"$addToSet": "$piece_id"},
                }
            },
        ]
    ).to_list(length=1)

    day_docs = await db[Collections.SESSIONS].aggregate(
        [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$started_at"}}
                }
            },
        ]
    ).to_list(length=2000)
    current_streak, longest_streak = _streaks({d["_id"] for d in day_docs})

    trend_docs = (
        await db[Collections.FEEDBACK]
        .find({"user_id": user_id}, {"pitch_accuracy": 1, "created_at": 1})
        .sort("created_at", 1)
        .to_list(length=60)
    )

    t = totals[0] if totals else {}
    return ProgressSummary(
        total_minutes=round(t.get("seconds", 0) / 60),
        total_sessions=t.get("sessions", 0),
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        pieces_practiced=len([p for p in t.get("pieces", []) if p]),
        recent_days=[
            DaySummary(date=d["_id"], minutes=round(d["seconds"] / 60), sessions=d["sessions"])
            for d in per_day
        ],
        pitch_accuracy_trend=[round(d.get("pitch_accuracy", 0.0), 3) for d in trend_docs],
    )
