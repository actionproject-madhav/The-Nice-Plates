#!/usr/bin/env python
"""Connection doctor.

Checks every external dependency and says exactly what is wrong and what to do
about it. Run this instead of guessing why something isn't working.

    python scripts/doctor.py

Exits non-zero if anything required is broken.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "platform"), str(ROOT / "audio")]

OK, WARN, BAD = "\033[32m  ok  \033[0m", "\033[33m warn \033[0m", "\033[31m FAIL \033[0m"
problems: list[str] = []


def say(state: str, label: str, detail: str = "") -> None:
    print(f"[{state}] {label}" + (f"\n         {detail}" if detail else ""))


def fail(label: str, detail: str, fix: str) -> None:
    say(BAD, label, detail)
    print(f"         \033[1mfix:\033[0m {fix}")
    problems.append(label)


def mask(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) < 12:
        return "***"
    return f"{value[:7]}…{value[-4:]}"


# ── .env ────────────────────────────────────────────────────────────────────


def check_env_file() -> None:
    print("\n\033[1m.env\033[0m")
    env = ROOT / ".env"
    if not env.exists():
        fail(".env exists", "No .env file.", "cp .env.example .env")
        return
    say(OK, ".env exists", str(env))

    text = env.read_text()
    if "<db_password>" in text:
        fail(
            "Atlas password substituted",
            "MONGODB_URI still contains the literal <db_password> placeholder.",
            "Replace <db_password> with the password you set under Atlas > Database Access.",
        )
    if re.search(r"^MONGODB_URI=.*<.*>", text, re.M):
        fail(
            "Atlas URI has no leftover placeholders",
            "MONGODB_URI still has a <...> placeholder in it.",
            "Paste the full string from Atlas > Connect > Drivers, with the password filled in.",
        )


# ── Mongo ───────────────────────────────────────────────────────────────────


async def check_mongo() -> None:
    print("\n\033[1mMongoDB\033[0m")
    from app.config import settings

    uri = settings.mongodb_uri
    is_atlas = uri.startswith("mongodb+srv://")
    say(OK, "URI configured", f"{'Atlas' if is_atlas else 'local'} · db={settings.mongodb_db}")

    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000, tz_aware=True)
    try:
        await client.admin.command("ping")
        say(OK, "Reachable")
    except Exception as exc:
        text = str(exc)
        if "bad auth" in text.lower() or "authentication failed" in text.lower():
            fix = (
                "Wrong username or password. Atlas > Database Access > Edit user > "
                "Edit Password. If the password has @ : / ? # or %, it must be "
                "percent-encoded in the URI."
            )
        elif "timed out" in text.lower() or "ServerSelectionTimeout" in text:
            fix = (
                "Atlas is not accepting this IP. Atlas > Network Access > Add IP Address "
                "> Allow access from anywhere (0.0.0.0/0). Render's free tier has no "
                "static egress IP, so an allowlist will not work."
            )
        elif "nodename nor servname" in text.lower() or "getaddrinfo" in text.lower():
            fix = "The cluster hostname doesn't resolve — check for a typo in the URI."
        else:
            fix = "Re-copy the string from Atlas > Connect > Drivers."
        fail("Reachable", text.split("\n")[0][:160], fix)
        return

    try:
        db = client[settings.mongodb_db]
        counts = {c: await db[c].count_documents({}) for c in ("users", "pieces", "practice_sessions")}
        say(OK, "Readable", " · ".join(f"{k}={v}" for k, v in counts.items()))
    except Exception as exc:
        fail(
            "Readable",
            str(exc)[:160],
            "The database user needs readWrite. Atlas > Database Access > Edit > "
            "Built-in Role: Read and write to any database.",
        )
    finally:
        client.close()


# ── OpenAI ──────────────────────────────────────────────────────────────────


def check_openai() -> None:
    print("\n\033[1mOpenAI\033[0m")
    from app.config import settings

    key = settings.openai_api_key
    if not key:
        fail(
            "API key set",
            "OPENAI_API_KEY is empty.",
            "Paste your key from platform.openai.com/api-keys into .env",
        )
        return
    if not key.startswith("sk-"):
        fail("API key looks valid", f"Key is {mask(key)}, expected it to start with sk-.",
             "Re-copy the key from platform.openai.com/api-keys")
        return
    say(OK, "API key set", mask(key))

    from openai import OpenAI

    client = OpenAI(api_key=key, timeout=30.0)

    try:
        models = {m.id for m in client.models.list()}
        say(OK, "Key accepted", f"{len(models)} models available")
    except Exception as exc:
        text = str(exc)
        if "401" in text or "invalid_api_key" in text:
            fix = "The key was rejected. It may have been revoked — make a new one."
        elif "429" in text or "quota" in text.lower():
            fix = (
                "The key works but the account has no credit. "
                "platform.openai.com/settings/organization/billing > add a payment method."
            )
        else:
            fix = "Check network access to api.openai.com."
        fail("Key accepted", text.split("\n")[0][:160], fix)
        return

    # The coach model
    model = settings.coach_model
    if model in models:
        say(OK, f"Coach model available", model)
    else:
        fail(
            "Coach model available",
            f"{model} is not on this key.",
            f"Set COACH_MODEL in .env to one you have. Cheap options present: "
            f"{', '.join(sorted(m for m in models if 'mini' in m)[:4]) or 'none found'}",
        )

    # Whisper, for voice notes
    if settings.whisper_model in models:
        say(OK, "Whisper available", settings.whisper_model)
    else:
        say(WARN, "Whisper available",
            f"{settings.whisper_model} not on this key; voice notes store without a transcript.")

    # A real round trip, with a tool call, because that is what the coach does.
    try:
        response = client.chat.completions.create(
            model=model if model in models else "gpt-4o-mini",
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=5,
        )
        reply = (response.choices[0].message.content or "").strip()
        usage = response.usage
        say(OK, "Live round trip", f"{reply!r} · {usage.total_tokens} tokens")
    except Exception as exc:
        fail("Live round trip", str(exc).split("\n")[0][:160],
             "The key authenticated but a completion failed — usually billing.")


# ── Redis, storage, auth ────────────────────────────────────────────────────


async def check_optional() -> None:
    print("\n\033[1mOptional\033[0m")
    from app.config import settings

    import redis.asyncio as aioredis

    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        say(OK, "Redis", "queue is instant")
    except Exception:
        say(WARN, "Redis", "not reachable — the worker falls back to a 30s Mongo sweep. Fine.")

    if settings.storage_configured:
        say(OK, "Cloudflare R2", f"bucket={settings.r2_bucket}")
    else:
        say(WARN, "Cloudflare R2", "not configured — uploads go to .localstorage/ on disk.")

    if settings.google_configured:
        say(OK, "Google sign-in", "configured")
    else:
        say(WARN, "Google sign-in",
            "not configured — use POST /v1/auth/dev-login (disabled when ENV=production).")


# ── main ────────────────────────────────────────────────────────────────────


async def main() -> int:
    print("\033[1mThe Nice Plates — connection doctor\033[0m")
    check_env_file()
    await check_mongo()
    check_openai()
    await check_optional()

    print("\n" + "─" * 64)
    if problems:
        print(f"\033[31m{len(problems)} problem(s):\033[0m " + ", ".join(problems))
        return 1
    print("\033[32mEverything required is connected.\033[0m")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    sys.exit(asyncio.run(main()))
