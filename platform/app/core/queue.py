"""The analysis queue.

Redis holds a list of job ids; Mongo holds the job's actual state. That split
matters: if Redis is wiped (free tiers do get wiped), no work is lost — a
sweeper can re-enqueue anything still `queued` in Mongo.

If Redis isn't reachable at all the enqueue is still recorded in Mongo and the
worker falls back to polling, so a missing REDIS_URL degrades latency rather
than breaking the feature.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

log = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


async def connect() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            _redis = client
            log.info("redis: connected")
        except Exception as exc:
            log.warning("redis: unavailable (%s); queue falls back to Mongo polling", exc)
            _redis = None
    return _redis


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def ping() -> bool:
    if _redis is None:
        return False
    try:
        await _redis.ping()
        return True
    except Exception:
        return False


async def enqueue(payload: dict[str, Any]) -> bool:
    """Push a job. Returns False if Redis took it nowhere (Mongo still has it)."""
    if _redis is None:
        return False
    try:
        await _redis.lpush(settings.analysis_queue, json.dumps(payload))
        return True
    except Exception as exc:
        log.warning("redis: enqueue failed (%s)", exc)
        return False


async def depth() -> int:
    if _redis is None:
        return 0
    try:
        return int(await _redis.llen(settings.analysis_queue))
    except Exception:
        return 0
