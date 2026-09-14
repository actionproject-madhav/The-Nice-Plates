#!/usr/bin/env python
"""End-to-end smoke test.

Drives the real API in-process with httpx's ASGI transport: sign in, create a
piece, chunk it, start a session, upload a take, wait for the worker to analyse
it, read the feedback back, and check the dashboard adds up.

No network, no Docker. Needs a Mongo it can reach (MONGODB_URI).

    python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "platform"), str(ROOT / "audio")]

os.environ.setdefault("MONGODB_DB", "nice_plates_smoke")

import httpx  # noqa: E402

PASS, FAIL = "  ok  ", " FAIL "
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{PASS if condition else FAIL}] {label}" + (f"  — {detail}" if detail else ""))
    if not condition:
        failures.append(label)


async def main() -> int:
    from app.main import app
    from app.core import db as db_module

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Reset the smoke database so runs are independent.
        async with app.router.lifespan_context(app):
            await db_module.get_db().client.drop_database(os.environ["MONGODB_DB"])

        async with app.router.lifespan_context(app):
            print("\n── health ──")
            r = await c.get("/health")
            check("GET /health", r.status_code == 200, r.text[:80])

            r = await c.get("/health/ready")
            body = r.json()
            check("GET /health/ready", r.status_code == 200, f"status={body['status']}")
            check("mongo reachable", body["checks"]["mongo"]["ok"])

            print("\n── auth ──")
            r = await c.post("/v1/auth/dev-login")
            check("POST /v1/auth/dev-login", r.status_code == 200, r.text[:120])
            if r.status_code != 200:
                return 1
            auth = r.json()
            token = auth["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            check("token issued", bool(token))

            r = await c.get("/v1/auth/me", headers=headers)
            check("GET /v1/auth/me", r.status_code == 200, r.json().get("email", ""))

            r = await c.get("/v1/pieces")
            check("unauthenticated request is rejected", r.status_code == 401)

            print("\n── repertoire ──")
            r = await c.post(
                "/v1/pieces",
                headers=headers,
                json={"title": "Gymnopédie No. 1", "composer": "Satie", "tempo_bpm": 72},
            )
            check("POST /v1/pieces", r.status_code == 201, r.text[:120])
            piece_id = r.json()["id"]

            r = await c.post(
                f"/v1/pieces/{piece_id}/chunk",
                headers=headers,
                json={"total_bars": 39, "bars_per_section": 4},
            )
            sections = r.json()
            check("POST chunk", r.status_code == 200, f"{len(sections)} sections")
            check("chunking covers every bar", sections[-1]["end_bar"] == 39,
                  f"last section ends at bar {sections[-1]['end_bar']}")
            check("sections are ordered", [s["index"] for s in sections] == list(range(len(sections))))
            section_id = sections[0]["id"]

            print("\n── practice session ──")
            r = await c.post(
                "/v1/sessions",
                headers=headers,
                json={"piece_id": piece_id, "section_id": section_id, "tempo_bpm": 66},
            )
            check("POST /v1/sessions", r.status_code == 201, r.text[:120])
            session_id = r.json()["id"]

            print("\n── recording upload ──")
            r = await c.post(
                "/v1/recordings/upload-url",
                headers=headers,
                json={
                    "filename": "take-1.webm",
                    "content_type": "audio/webm",
                    "session_id": session_id,
                    "piece_id": piece_id,
                    "section_id": section_id,
                },
            )
            check("POST /v1/recordings/upload-url", r.status_code == 200, r.text[:140])
            ticket = r.json()
            check("presigned ticket returned", bool(ticket["upload_url"]),
                  f"backend={ticket['backend']}")
            recording_id = ticket["recording_id"]

            r = await c.post(
                "/v1/recordings/upload-url",
                headers=headers,
                json={"filename": "x.txt", "content_type": "text/plain"},
            )
            check("non-audio upload is refused", r.status_code == 415)

            # The bytes the browser would PUT. Fake WebM; the stub engine hashes it.
            audio = b"\x1aE\xdf\xa3" + bytes(range(256)) * 40
            r = await c.put(ticket["upload_url"], content=audio,
                            headers={"Content-Type": "audio/webm"})
            check("PUT bytes to storage", r.status_code == 200, r.text[:80])

            r = await c.post(
                f"/v1/recordings/{recording_id}/complete",
                headers=headers,
                json={"size_bytes": len(audio), "duration_seconds": 6.2},
            )
            check("POST complete", r.status_code == 200, r.text[:140])
            check("job enqueued", "job_id" in r.json(), r.json().get("queued_via", ""))

            print("\n── analysis (embedded worker) ──")
            feedback = None
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                await asyncio.sleep(1.0)
                r = await c.get(f"/v1/recordings/{recording_id}", headers=headers)
                status = r.json()
                if status["status"] in ("analyzed", "failed"):
                    feedback = status.get("feedback")
                    break
            check("worker picked the job up and finished", status["status"] == "analyzed",
                  f"status={status['status']} job={status.get('job_status')} "
                  f"err={status.get('error')}")
            check("feedback was written", feedback is not None)
            if feedback:
                check("pitch accuracy in range", 0.0 <= feedback["pitch_accuracy"] <= 1.0,
                      f"{feedback['pitch_accuracy']:.2f}")
                check("timing accuracy in range", 0.0 <= feedback["timing_accuracy"] <= 1.0,
                      f"{feedback['timing_accuracy']:.2f}")
                check("notes were detected", feedback["notes_played"] > 0,
                      f"{feedback['notes_played']} notes, engine={feedback['engine']}")
                check("summary is human-readable", len(feedback["summary"]) > 20,
                      feedback["summary"])
                check("bar numbers start inside the section",
                      not feedback["problem_bars"] or min(feedback["problem_bars"]) >= 1)

            print("\n── session close & dashboard ──")
            r = await c.post(
                f"/v1/sessions/{session_id}/end",
                headers=headers,
                json={"duration_seconds": 1500, "notes": "Left hand still rushing."},
            )
            check("POST session end", r.status_code == 200, r.text[:100])

            r = await c.post(
                f"/v1/sessions/{session_id}/end", headers=headers,
                json={"duration_seconds": 60},
            )
            check("ending a session twice is refused", r.status_code == 409)

            r = await c.get("/v1/progress/summary", headers=headers)
            summary = r.json()
            check("GET /v1/progress/summary", r.status_code == 200, r.text[:100])
            check("minutes rolled up", summary["total_minutes"] == 25,
                  f"{summary['total_minutes']} min")
            check("streak counted", summary["current_streak_days"] == 1,
                  f"{summary['current_streak_days']} day")
            check("pieces counted", summary["pieces_practiced"] == 1)
            check("accuracy trend populated", len(summary["pitch_accuracy_trend"]) >= 1)

            print("\n── coach ──")
            r = await c.post("/v1/coach/ask", headers=headers,
                             json={"message": "How am I doing?"})
            from app.config import settings
            if settings.coach_configured:
                check("POST /v1/coach/ask", r.status_code == 200, r.text[:200])
                if r.status_code == 200:
                    print(f"        reply: {r.json()['reply'][:160]}")
                    print(f"        tools: {r.json()['tools_used']}")
            else:
                check("coach reports itself unconfigured (no API key set)",
                      r.status_code == 503, r.json().get("detail", "")[:90])

            # The tools still have to work without a key — that's our code, not the model's.
            from app.services import coach as coach_service
            db = db_module.get_db()
            user_id = auth["user"]["id"]
            hist = await coach_service.run_tool(db, user_id, "get_practice_history", {})
            check("coach tool: practice history", hist["session_count"] == 1,
                  f"{hist['total_minutes']} min over {hist['session_count']} session")
            fb = await coach_service.run_tool(db, user_id, "get_recent_feedback", {})
            check("coach tool: recent feedback", fb["count"] >= 1)
            rep = await coach_service.run_tool(db, user_id, "get_repertoire", {})
            check("coach tool: repertoire", rep["count"] == 1 and rep["pieces"][0]["sections"] == 10,
                  f"{rep['count']} piece, {rep['pieces'][0]['sections']} sections")

            print("\n── tenancy ──")
            r2 = await c.post("/v1/auth/dev-login", params={"email": "other@nice-plates.local"})
            other = {"Authorization": f"Bearer {r2.json()['access_token']}"}
            r = await c.get(f"/v1/pieces/{piece_id}", headers=other)
            check("another user cannot read this piece", r.status_code == 404)
            r = await c.get(f"/v1/recordings/{recording_id}", headers=other)
            check("another user cannot read this recording", r.status_code == 404)
            r = await c.get("/v1/pieces", headers=other)
            check("another user's library is empty", r.json() == [])

    print("\n" + "─" * 62)
    if failures:
        print(f"{len(failures)} FAILED: " + ", ".join(failures))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
