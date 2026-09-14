"""Request and response bodies.

Distinct from `nplates_data.models`, which describes what is *stored*. These
describe what crosses the wire, which is deliberately narrower — a client can
never set `owner_id`, for example.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from nplates_data.models import Feedback, NoteComparison, Piece, Section


# ── Auth ──
class GoogleLoginRequest(BaseModel):
    credential: str = Field(description="The ID token from Google Identity Services.")


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: "UserPublic"


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    picture: str | None = None
    role: str
    instrument: str | None = None


# ── Pieces & sections ──
class PieceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    composer: str | None = Field(default=None, max_length=200)
    instrument: str | None = None
    tempo_bpm: int | None = Field(default=None, ge=20, le=300)
    time_signature: str | None = None
    key_signature: str | None = None
    tags: list[str] = Field(default_factory=list)


class PieceUpdate(BaseModel):
    title: str | None = None
    composer: str | None = None
    instrument: str | None = None
    tempo_bpm: int | None = Field(default=None, ge=20, le=300)
    time_signature: str | None = None
    key_signature: str | None = None
    score_key: str | None = None
    score_pages: int | None = None
    tags: list[str] | None = None


class SectionCreate(BaseModel):
    label: str
    start_bar: int = Field(ge=1)
    end_bar: int = Field(ge=1)
    page: int = Field(default=1, ge=1)
    difficulty: int = Field(default=3, ge=1, le=5)


class ChunkRequest(BaseModel):
    """Ask the server to split a piece into practice sections."""

    total_bars: int = Field(ge=1, le=2000)
    bars_per_section: int = Field(default=4, ge=1, le=32)
    replace_existing: bool = True


# ── Practice ──
class SessionStart(BaseModel):
    piece_id: str | None = None
    section_id: str | None = None
    tempo_bpm: int | None = Field(default=None, ge=20, le=300)


class SessionEnd(BaseModel):
    duration_seconds: int = Field(ge=0, le=60 * 60 * 12)
    notes: str | None = Field(default=None, max_length=2000)


# ── Recordings ──
class UploadRequest(BaseModel):
    filename: str = Field(default="take.webm")
    content_type: str = Field(default="audio/webm")
    # "performance" goes to the note transcriber, "voice_note" to Whisper.
    kind: Literal["performance", "voice_note"] = "performance"
    session_id: str | None = None
    piece_id: str | None = None
    section_id: str | None = None


class UploadTicket(BaseModel):
    recording_id: str
    key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in: int
    backend: str


class UploadComplete(BaseModel):
    size_bytes: int = Field(default=0, ge=0)
    duration_seconds: float | None = None


class RecordingStatus(BaseModel):
    recording_id: str
    status: str
    kind: str = "performance"
    job_status: str | None = None
    feedback: Feedback | None = None
    transcript: str | None = None
    playback_url: str | None = None
    error: str | None = None


# ── Progress ──
class DaySummary(BaseModel):
    date: str
    minutes: int
    sessions: int


class ProgressSummary(BaseModel):
    total_minutes: int
    total_sessions: int
    current_streak_days: int
    longest_streak_days: int
    pieces_practiced: int
    recent_days: list[DaySummary]
    pitch_accuracy_trend: list[float]


# ── Coach ──
class CoachMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CoachRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None
    piece_id: str | None = None


class CoachResponse(BaseModel):
    thread_id: str
    reply: str
    tools_used: list[str] = Field(default_factory=list)
    model: str


AuthResponse.model_rebuild()
