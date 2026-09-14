#!/usr/bin/env python
"""Prove the voice-note path works, with real recorded speech.

Generates an actual spoken sentence with macOS `say`, pushes it through the
real API — presign, upload, enqueue — lets the real worker pick it up, calls
the real Whisper API, and checks that what comes back resembles what was said
and lands in the session's notes.

    python scripts/test_voice_note.py

Needs OPENAI_API_KEY. Without it the test still runs and verifies every step
except the transcription itself, and says so.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "platform"), str(ROOT / "audio")]

os.environ.setdefault("MONGODB_DB", "nice_plates_voicetest")

import httpx  # noqa: E402

SPOKEN = (
    "Worked bars twelve to sixteen today. The left hand is still rushing "
    "through the arpeggio. Tempo was around seventy two."
)
# Words that must survive transcription for us to call it working.
MUST_HEAR = ["bar", "left hand", "rush"]

PASS, FAIL, SKIP = "\033[32m  ok  \033[0m", "\033[31m FAIL \033[0m", "\033[33m skip \033[0m"
failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{PASS if ok else FAIL}] {label}" + (f"  — {detail}" if detail else ""))
    if not ok:
        failures.append(label)
    return ok


def record_speech(path: Path) -> bool:
    """Synthesize real speech. This is a stand-in for a human at a microphone."""
    if not shutil.which("say"):
        return False
    subprocess.run(
        ["say", "-o", str(path), "--data-format=LEI16@22050", SPOKEN],
        check=True,
        capture_output=True,
    )
    return path.exists() and path.stat().st_size > 1000


async def main() -> int:
    from app.config import settings
    from app.core import db as db_module
    from app.main import app
    from nplates_data.collections import Collections

    print("\033[1mVoice note — end to end\033[0m")
    print(f'Saying: "{SPOKEN}"\n')

    tmp = Path(tempfile.mkdtemp())
    audio = tmp / "note.wav"
    if not check("recorded real speech with `say`", record_speech(audio),
                 f"{audio.stat().st_size // 1024}KB wav" if audio.exists() else "no `say` binary"):
        return 1

    has_key = settings.coach_configured
    if not has_key:
        print(f"[{SKIP}] OPENAI_API_KEY is not set — transcription will be skipped\n")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        async with app.router.lifespan_context(app):
            await db_module.get_db().client.drop_database(os.environ["MONGODB_DB"])

        async with app.router.lifespan_context(app):
            r = await c.post("/v1/auth/dev-login")
            headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

            r = await c.post("/v1/pieces", headers=headers,
                             json={"title": "Prelude in C", "composer": "J.S. Bach"})
            piece_id = r.json()["id"]
            r = await c.post("/v1/sessions", headers=headers, json={"piece_id": piece_id})
            session_id = r.json()["id"]

            r = await c.post(
                "/v1/recordings/upload-url",
                headers=headers,
                json={
                    "filename": "note.wav",
                    "content_type": "audio/wav",
                    "kind": "voice_note",
                    "session_id": session_id,
                    "piece_id": piece_id,
                },
            )
            check("API issued a presigned upload for kind=voice_note",
                  r.status_code == 200, r.text[:120])
            ticket = r.json()
            check("voice notes are keyed separately from takes",
                  ticket["key"].startswith("notes/"), ticket["key"])

            body = audio.read_bytes()
            r = await c.put(ticket["upload_url"], content=body,
                            headers={"Content-Type": "audio/wav"})
            check("uploaded the audio", r.status_code == 200)

            r = await c.post(f"/v1/recordings/{ticket['recording_id']}/complete",
                             headers=headers, json={"size_bytes": len(body)})
            check("queued for analysis", r.status_code == 200, r.text[:100])

            print("\n  waiting for the worker…")
            status = {}
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                await asyncio.sleep(1.5)
                status = (await c.get(f"/v1/recordings/{ticket['recording_id']}",
                                      headers=headers)).json()
                if status["status"] in ("analyzed", "failed"):
                    break

            check("worker finished the job", status.get("status") == "analyzed",
                  f"status={status.get('status')} err={status.get('error')}")
            check("worker routed it to Whisper, not the note transcriber",
                  status.get("kind") == "voice_note", f"kind={status.get('kind')}")

            transcript = (status.get("transcript") or "").strip()
            if has_key:
                check("Whisper returned a transcript", bool(transcript), f"{len(transcript)} chars")
                if transcript:
                    print(f"\n  \033[1mheard:\033[0m {transcript}\n")
                    lower = transcript.lower()
                    for phrase in MUST_HEAR:
                        check(f'heard "{phrase}"', phrase in lower)

                    r = await c.get("/v1/sessions", headers=headers)
                    notes = (r.json()[0].get("notes") or "")
                    check("transcript was appended to the session's notes",
                          transcript[:30] in notes, notes[:80])

                    # The whole point: the coach can now read what was said.
                    from app.services import coach as coach_service
                    db = db_module.get_db()
                    user = await db[Collections.USERS].find_one({"email": "dev@nice-plates.local"})
                    history = await coach_service.run_tool(
                        db, str(user["_id"]), "get_practice_history", {}
                    )
                    session_notes = (history["sessions"][0].get("notes") or "")
                    check("the coach's tool surfaces the spoken note",
                          "bar" in session_notes.lower(), session_notes[:70])
            else:
                check("stored the note without failing the job when no key is set",
                      transcript == "" and status.get("status") == "analyzed")

    shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "─" * 62)
    if failures:
        print(f"\033[31m{len(failures)} failed:\033[0m " + ", ".join(failures))
        return 1
    print("\033[32mvoice note path verified" + ("" if has_key else " (transcription skipped — no key)") + "\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
