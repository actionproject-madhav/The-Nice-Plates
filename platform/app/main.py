"""API entrypoint.

Run locally:   uvicorn app.main:app --reload --app-dir platform
Docs:          http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core import db as db_module
from app.core import queue
from app.routers import auth, coach, health, pieces, progress, recordings, sessions
from nplates_data.indexes import ensure_indexes

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("nice-plates")

API_PREFIX = "/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database = await db_module.connect()
    await queue.connect()

    try:
        applied = await ensure_indexes(database)
        log.info("mongo: %d indexes ensured", len(applied))
    except Exception as exc:
        # An unreachable Mongo shouldn't stop the process — /health/ready will
        # report it, and the container stays up long enough to read the logs.
        log.error("mongo: could not ensure indexes (%s)", exc)

    worker_task: asyncio.Task | None = None
    if settings.embedded_worker:
        from app.worker_runner import run_embedded_worker

        worker_task = asyncio.create_task(run_embedded_worker())
        log.info("worker: running in-process (set EMBEDDED_WORKER=false to split it out)")

    yield

    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    await queue.close()
    await db_module.close()


app = FastAPI(
    title="The Nice Plates API",
    description="Practice tracking, recording analysis and coaching for musicians.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something broke on our end. We're looking at it."},
    )


app.include_router(health.router)
for r in (auth.router, pieces.router, sessions.router, recordings.router,
          progress.router, coach.router):
    app.include_router(r, prefix=API_PREFIX)
app.include_router(recordings.local_router, prefix=API_PREFIX)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": "the-nice-plates-api",
        "version": app.version,
        "docs": "/docs",
        "health": "/health/ready",
    }
