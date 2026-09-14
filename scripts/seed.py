#!/usr/bin/env python
"""Seed a demo musician with four weeks of practice.

Gives the dashboard, the ledger and the coach something real to read before
anyone has recorded a note. Idempotent: re-running replaces the demo user's
data rather than stacking another month on top.

    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "platform"), str(ROOT / "audio")]

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.config import settings  # noqa: E402
from nplates_data.collections import Collections  # noqa: E402
from nplates_data.indexes import ensure_indexes  # noqa: E402
from nplates_data.models import (  # noqa: E402
    Feedback,
    Piece,
    PracticeSession,
    Recording,
    Section,
    User,
    utcnow,
)

# Matches POST /v1/auth/dev-login exactly, so `make seed` then "Dev sign-in"
# drops you straight into a month of practice history.
DEMO_EMAIL = "dev@nice-plates.local"

REPERTOIRE = [
    ("Gymnopédie No. 1", "Satie", 72, 39),
    ("Prelude in C", "J.S. Bach", 66, 35),
    ("Clair de Lune", "Debussy", 60, 72),
]


async def main() -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri, tz_aware=True)
    db = client[settings.mongodb_db]
    await ensure_indexes(db)

    rng = random.Random(20260914)  # deterministic: the demo looks the same every time

    user = User(
        google_sub=f"dev|{DEMO_EMAIL}",
        email=DEMO_EMAIL,
        name="Dev User",
        instrument="piano",
    )
    on_insert = user.to_mongo()
    on_insert.pop("last_login_at", None)
    await db[Collections.USERS].update_one(
        {"google_sub": user.google_sub},
        {"$set": {"last_login_at": utcnow()}, "$setOnInsert": on_insert},
        upsert=True,
    )
    user_doc = await db[Collections.USERS].find_one({"google_sub": user.google_sub})
    user_id = str(user_doc["_id"])

    # Clear this user's history so a re-run doesn't stack another month on top.
    for collection in (
        Collections.PIECES,
        Collections.SESSIONS,
        Collections.RECORDINGS,
        Collections.FEEDBACK,
        Collections.JOBS,
    ):
        field = "owner_id" if collection == Collections.PIECES else "user_id"
        await db[collection].delete_many({field: user_id})
    await db[Collections.SECTIONS].delete_many({"owner_id": user_id})

    piece_ids: list[str] = []
    for title, composer, tempo, bars in REPERTOIRE:
        piece = Piece(
            owner_id=user_id, title=title, composer=composer, tempo_bpm=tempo, instrument="piano"
        )
        result = await db[Collections.PIECES].insert_one(piece.to_mongo())
        piece_id = str(result.inserted_id)
        piece_ids.append(piece_id)

        sections = [
            Section(
                piece_id=piece_id,
                owner_id=user_id,
                index=i,
                label=f"Bars {start}–{min(start + 3, bars)}",
                start_bar=start,
                end_bar=min(start + 3, bars),
            )
            for i, start in enumerate(range(1, bars + 1, 4))
        ]
        await db[Collections.SECTIONS].insert_many([s.to_mongo() for s in sections])

    now = datetime.now(timezone.utc)
    sessions = 0
    recordings = 0

    for days_ago in range(27, -1, -1):
        # Practise most days, with a believable couple of gaps.
        if rng.random() < 0.22:
            continue
        day = now - timedelta(days=days_ago, hours=rng.randint(0, 6))
        piece_id = piece_ids[rng.randrange(len(piece_ids))]
        duration = rng.choice([900, 1200, 1500, 1800, 2400])

        session = PracticeSession(
            user_id=user_id,
            piece_id=piece_id,
            started_at=day,
            ended_at=day + timedelta(seconds=duration),
            duration_seconds=duration,
            tempo_bpm=rng.choice([60, 66, 72, 80]),
        )
        session.created_at = day
        session.updated_at = day
        session_result = await db[Collections.SESSIONS].insert_one(session.to_mongo())
        sessions += 1

        if rng.random() < 0.55:
            continue

        # Accuracy trends upward over the month, with noise — the shape the
        # dashboard is meant to reveal.
        progress = (27 - days_ago) / 27
        pitch = min(0.99, 0.62 + progress * 0.28 + rng.uniform(-0.05, 0.05))
        timing = min(0.99, 0.55 + progress * 0.30 + rng.uniform(-0.06, 0.06))

        recording = Recording(
            user_id=user_id,
            session_id=str(session_result.inserted_id),
            piece_id=piece_id,
            storage_key=f"recordings/{user_id}/seed/{days_ago}.webm",
            status="analyzed",
            size_bytes=rng.randint(200_000, 900_000),
            duration_seconds=round(rng.uniform(25, 95), 1),
        )
        recording.created_at = day
        recording.updated_at = day
        recording_result = await db[Collections.RECORDINGS].insert_one(recording.to_mongo())
        recordings += 1

        problem_bars = sorted(rng.sample(range(1, 33), rng.randint(1, 4)))
        feedback = Feedback(
            user_id=user_id,
            recording_id=str(recording_result.inserted_id),
            piece_id=piece_id,
            pitch_accuracy=round(pitch, 4),
            timing_accuracy=round(timing, 4),
            tempo_bpm_detected=round(rng.uniform(58, 84), 1),
            tempo_stability=round(min(0.98, 0.6 + progress * 0.3), 3),
            notes_expected=rng.randint(40, 120),
            notes_played=rng.randint(40, 120),
            problem_bars=problem_bars,
            summary=(
                f"{pitch:.0%} of notes at the right pitch, {timing:.0%} in time; "
                f"roughest around bars {', '.join(str(b) for b in problem_bars)}."
            ),
            engine="seed",
        )
        feedback.created_at = day
        feedback.updated_at = day
        await db[Collections.FEEDBACK].update_one(
            {"recording_id": feedback.recording_id}, {"$set": feedback.to_mongo()}, upsert=True
        )

    print(f"Seeded {DEMO_EMAIL}")
    print(f"  {len(REPERTOIRE)} pieces, {sessions} sessions, {recordings} analysed recordings")
    print(f"  database: {settings.mongodb_db}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
