"""Index definitions, applied on API startup and by `make seed`.

Keeping these in the shared package means the worker and the API agree about
what is unique. Every index here exists because a query in the codebase needs
it; adding one without a query is how you slow down writes for free.
"""

from __future__ import annotations

from typing import Any

from nplates_data.collections import Collections

# (collection, keys, options)
INDEXES: list[tuple[str, list[tuple[str, int]], dict[str, Any]]] = [
    (Collections.USERS, [("google_sub", 1)], {"unique": True, "name": "uniq_google_sub"}),
    (Collections.USERS, [("email", 1)], {"unique": True, "name": "uniq_email"}),

    (Collections.PIECES, [("owner_id", 1), ("updated_at", -1)], {"name": "owner_recent"}),

    (Collections.SECTIONS, [("piece_id", 1), ("index", 1)], {"name": "piece_order"}),

    # The dashboard's hot path: this user's sessions, newest first.
    (Collections.SESSIONS, [("user_id", 1), ("started_at", -1)], {"name": "user_recent"}),
    (Collections.SESSIONS, [("piece_id", 1), ("started_at", -1)], {"name": "piece_recent"}),

    (Collections.RECORDINGS, [("user_id", 1), ("created_at", -1)], {"name": "user_recent"}),
    (Collections.RECORDINGS, [("storage_key", 1)], {"unique": True, "name": "uniq_key"}),

    (Collections.FEEDBACK, [("recording_id", 1)], {"unique": True, "name": "uniq_recording"}),
    (Collections.FEEDBACK, [("user_id", 1), ("created_at", -1)], {"name": "user_recent"}),

    (Collections.JOBS, [("status", 1), ("created_at", 1)], {"name": "queue_scan"}),
    (Collections.JOBS, [("recording_id", 1)], {"name": "by_recording"}),

    (Collections.COACH_THREADS, [("user_id", 1), ("updated_at", -1)], {"name": "user_recent"}),
]


async def ensure_indexes(db) -> list[str]:
    """Idempotent. Safe to run on every boot."""
    applied = []
    for collection, keys, options in INDEXES:
        await db[collection].create_index(keys, **options)
        applied.append(f"{collection}.{options.get('name')}")
    return applied
