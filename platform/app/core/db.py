"""Mongo connection lifecycle.

A single AsyncIOMotorClient for the process, opened on startup and closed on
shutdown. Motor pools connections internally; creating a client per request is
the classic way to exhaust an M0 cluster's 500-connection limit.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

log = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


async def connect() -> AsyncIOMotorDatabase:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5_000,
            maxPoolSize=20,  # M0 allows 500 total; leave room for the worker.
            tz_aware=True,
        )
        log.info("mongo: connecting to db=%s", settings.mongodb_db)
    return _client[settings.mongodb_db]


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Mongo client not initialised; call connect() in the lifespan.")
    return _client[settings.mongodb_db]


async def ping() -> bool:
    try:
        await get_db().command("ping")
        return True
    except Exception:
        return False
