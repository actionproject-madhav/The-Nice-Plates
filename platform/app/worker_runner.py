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

# audio/ is a sibling of platform/ in the repo, not an installed package.
AUDIO_DIR = Path(__file__).resolve().parents[2] / "audio"
if str(AUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIO_DIR))


async def run_embedded_worker() -> None:
    try:
        from worker import worker_loop
    except ImportError as exc:
        log.error("worker: could not import audio/worker.py (%s); analysis is disabled", exc)
        return

    while True:
        try:
            await worker_loop()
        except asyncio.CancelledError:
            log.info("worker: stopping")
            raise
        except Exception:
            log.exception("worker: loop crashed; restarting in 5s")
            await asyncio.sleep(5)
