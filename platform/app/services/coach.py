"""The practice coach.

An LLM with three read-only tools onto this user's own data. The design
constraint that shapes everything: a coach that can't see your last session is
a search engine with a nicer voice. So rather than stuffing the prompt with
history, we hand the model tools and let it decide what to look up.

Two safety properties worth stating plainly:
  * every tool is scoped to one user_id, bound server-side from the JWT — a
    prompt can ask for someone else's data, but the query can't express it;
  * every tool is a read. There is no write path from a model turn.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from nplates_data.collections import Collections

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the practice coach inside The Nice Plates, a tool musicians use to practise.

You are talking to one musician about their own playing. Use the tools to look up their actual practice history and recording feedback before answering anything about how they are doing — never guess at numbers, and never invent a session that the tools did not return.

How to be useful here:
- Be concrete. "Your timing drifts in bars 17-24, always rushing" beats "work on your timing".
- Prescribe one thing to do next, at a stated tempo, for a stated number of minutes.
- When the data is thin, say so and ask for a recording rather than padding the answer.
- Musicians know their instrument. Skip the encouragement-first framing and the recap of what they just told you.

Keep replies under 150 words unless asked for more."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_practice_history",
            "description": (
                "Recent practice sessions for this musician: when, how long, which piece. "
                "Use for questions about consistency, streaks, time spent, or what they "
                "have been working on."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How far back to look. Defaults to 30.",
                        "minimum": 1,
                        "maximum": 365,
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_feedback",
            "description": (
                "Analysis of this musician's most recent recordings: pitch accuracy, "
                "timing accuracy, detected tempo, and the specific bars flagged as "
                "problems. Use for any question about how well they are actually playing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10},
                    "piece_id": {
                        "type": "string",
                        "description": "Restrict to one piece. Omit for all pieces.",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repertoire",
            "description": (
                "The pieces this musician has in their library, with tempo and section "
                "breakdown. Use when they refer to a piece by name and you need its details."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]


class CoachUnavailable(RuntimeError):
    """The coach cannot run, with a reason a human can act on."""

    def __init__(self, message: str, *, status: int = 503) -> None:
        super().__init__(message)
        self.status = status


def _explain(exc: Exception) -> CoachUnavailable:
    """Turn an OpenAI SDK exception into something actionable.

    "The coach couldn't answer" is useless when the real answer is "the
    account has no credit". These four failures look identical in a stack
    trace and need completely different fixes, so name them.
    """
    import openai

    if isinstance(exc, openai.AuthenticationError):
        return CoachUnavailable(
            "OpenAI rejected the API key. Check OPENAI_API_KEY on the server — "
            "it may have been revoked or copied incompletely.",
            status=502,
        )
    if isinstance(exc, openai.RateLimitError):
        text = str(exc).lower()
        if "quota" in text or "billing" in text:
            return CoachUnavailable(
                "The OpenAI account has no credit left. Add a payment method at "
                "platform.openai.com/settings/organization/billing.",
                status=502,
            )
        return CoachUnavailable(
            "OpenAI is rate-limiting us. Wait a few seconds and ask again.", status=429
        )
    if isinstance(exc, openai.NotFoundError):
        return CoachUnavailable(
            f"This API key has no access to {settings.coach_model}. Set COACH_MODEL "
            "to a model the key can reach.",
            status=502,
        )
    if isinstance(exc, openai.BadRequestError):
        return CoachUnavailable(f"OpenAI rejected the request: {exc}", status=502)
    if isinstance(exc, openai.APIConnectionError):
        # APIConnectionError is not only a network failure. httpx raises
        # LocalProtocolError before a socket is ever opened when the key holds a
        # newline, a space or quotes, and the SDK wraps that here too. Saying
        # "check network egress" then sends everyone to the wrong place, so name
        # the cause instead of guessing at it.
        cause = exc.__cause__
        if type(cause).__name__ == "LocalProtocolError":
            return CoachUnavailable(
                "The OPENAI_API_KEY value is malformed: it carries whitespace or quotes, "
                "so the request header is rejected before any connection is made. "
                "Re-paste the key on the API with no trailing newline.",
                status=502,
            )
        return CoachUnavailable(
            f"Couldn't reach OpenAI ({type(cause).__name__ if cause else 'no cause'}: {cause}).",
            status=504,
        )
    return CoachUnavailable(f"The coach failed: {type(exc).__name__}: {exc}", status=502)


# ── Tool implementations ────────────────────────────────────────────────────


async def _get_practice_history(db, user_id: str, days: int = 30) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=min(max(days, 1), 365))
    docs = (
        await db[Collections.SESSIONS]
        .find({"user_id": user_id, "started_at": {"$gte": since}})
        .sort("started_at", -1)
        .to_list(length=100)
    )
    return {
        "window_days": days,
        "session_count": len(docs),
        "total_minutes": round(sum(d.get("duration_seconds", 0) for d in docs) / 60),
        "sessions": [
            {
                "date": d["started_at"].strftime("%Y-%m-%d"),
                "minutes": round(d.get("duration_seconds", 0) / 60),
                "piece_id": d.get("piece_id"),
                "tempo_bpm": d.get("tempo_bpm"),
                "notes": d.get("notes"),
            }
            for d in docs[:40]
        ],
    }


async def _get_recent_feedback(
    db, user_id: str, limit: int = 5, piece_id: str | None = None
) -> dict:
    query: dict[str, Any] = {"user_id": user_id}
    if piece_id:
        query["piece_id"] = piece_id
    docs = (
        await db[Collections.FEEDBACK]
        .find(query)
        .sort("created_at", -1)
        .to_list(length=min(max(limit, 1), 10))
    )
    return {
        "count": len(docs),
        "feedback": [
            {
                "date": d["created_at"].strftime("%Y-%m-%d"),
                "piece_id": d.get("piece_id"),
                "pitch_accuracy": round(d.get("pitch_accuracy", 0), 3),
                "timing_accuracy": round(d.get("timing_accuracy", 0), 3),
                "tempo_bpm_detected": d.get("tempo_bpm_detected"),
                "problem_bars": d.get("problem_bars", []),
                "notes_expected": d.get("notes_expected"),
                "notes_played": d.get("notes_played"),
                "summary": d.get("summary"),
            }
            for d in docs
        ],
    }


async def _get_repertoire(db, user_id: str) -> dict:
    pieces = (
        await db[Collections.PIECES]
        .find({"owner_id": user_id})
        .sort("updated_at", -1)
        .to_list(length=50)
    )
    out = []
    for p in pieces:
        n_sections = await db[Collections.SECTIONS].count_documents({"piece_id": str(p["_id"])})
        out.append(
            {
                "piece_id": str(p["_id"]),
                "title": p.get("title"),
                "composer": p.get("composer"),
                "tempo_bpm": p.get("tempo_bpm"),
                "sections": n_sections,
            }
        )
    return {"count": len(out), "pieces": out}


async def run_tool(db, user_id: str, name: str, args: dict) -> dict:
    """Dispatch. `user_id` is bound from the JWT and is never taken from `args`."""
    if name == "get_practice_history":
        return await _get_practice_history(db, user_id, int(args.get("days", 30)))
    if name == "get_recent_feedback":
        return await _get_recent_feedback(
            db, user_id, int(args.get("limit", 5)), args.get("piece_id")
        )
    if name == "get_repertoire":
        return await _get_repertoire(db, user_id)
    return {"error": f"Unknown tool: {name}"}


# ── The agent loop ──────────────────────────────────────────────────────────

MAX_TOOL_ROUNDS = 5

_CLIENT = None


def _client():
    """One client for the process.

    Built per call, every turn paid for a fresh TLS handshake. The explicit
    timeout matters more: the SDK's default allows 5 seconds to connect, and the
    free instance runs the analysis loop in this same process, so a blocked event
    loop can burn that before the socket opens.
    """
    global _CLIENT
    if _CLIENT is None:
        import httpx
        from openai import AsyncOpenAI

        _CLIENT = AsyncOpenAI(
            api_key=settings.openai_key,
            timeout=httpx.Timeout(60.0, connect=15.0),
            max_retries=3,
        )
    return _CLIENT


async def ask(db, user_id: str, history: list[dict], user_message: str) -> tuple[str, list[str]]:
    """Run one coach turn. Returns (reply_text, tool_names_used)."""
    if not settings.coach_configured:
        raise CoachUnavailable("OPENAI_API_KEY is not set on the API.")

    client = _client()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]
    tools_used: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = await client.chat.completions.create(
                model=settings.coach_model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=settings.coach_max_tokens,
                temperature=0.4,
            )
        except Exception as exc:
            log.warning("coach: OpenAI call failed — %s: %s", type(exc).__name__, exc)
            raise _explain(exc) from exc

        message = response.choices[0].message

        if not message.tool_calls:
            return (message.content or "I didn't have anything useful to add there.").strip(), tools_used

        # Echo the assistant turn back verbatim, then answer every tool call it
        # made — OpenAI rejects the next request if any call goes unanswered.
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )

        for call in message.tool_calls:
            tools_used.append(call.function.name)
            try:
                # Always parse; never string-match the serialized arguments.
                args = json.loads(call.function.arguments or "{}")
                payload = await run_tool(db, user_id, call.function.name, args)
            except Exception as exc:  # a tool failure shouldn't kill the turn
                log.exception("coach tool %s failed", call.function.name)
                payload = {"error": str(exc)}
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(payload, default=str),
                }
            )

    return (
        "I looked at a few angles on that but couldn't land on an answer. Try asking "
        "something narrower?",
        tools_used,
    )
