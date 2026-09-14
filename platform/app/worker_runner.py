"""Adapter that runs the ML worker inside the API process.

Render's free tier has no background workers, so for v0 the analysis loop lives
in the API's event loop. `audio/worker.py` is the same code running standalone;
when the worker moves to its own service, set EMBEDDED_WORKER=false and nothing
else changes.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# "embedded_worker: true" in config says nothing about whether the loop is
# actually running. This says.
STATUS: dict = {"state": "not_started", "error": None}

# audio/ is a sibling of platform/ in the repo, not an installed package.
AUDIO_DIR = Path(__file__).resolve().parents[2] / "audio"
if str(AUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIO_DIR))


async def run_embedded_worker() -> None:
    try:
        from worker import HEARTBEAT, worker_loop
    except Exception as exc:
        STATUS.update(state="import_failed", error=f"{type(exc).__name__}: {exc}"[:300])
        log.error("worker: could not import audio/worker.py (%s); analysis is disabled", exc)
        return

    STATUS["heartbeat"] = HEARTBEAT

    while True:
        try:
            STATUS["state"] = "running"
            await worker_loop()
        except asyncio.CancelledError:
            STATUS["state"] = "stopped"
            log.info("worker: stopping")
            raise
        except Exception as exc:
            STATUS.update(state="restarting", error=f"{type(exc).__name__}: {exc}"[:300])
            log.exception("worker: loop crashed; restarting in 5s")
            await asyncio.sleep(5)
