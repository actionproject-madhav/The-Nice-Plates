"""Domain models.

Every document stored in Mongo has a model here. `MongoModel` handles the one
piece of impedance mismatch that matters: Mongo's `_id` is an ObjectId, and we
expose it to the API and the frontend as a string `id`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Accept an ObjectId, a string, or anything str()-able coming back from motor.
ObjectIdStr = Annotated[str, BeforeValidator(lambda v: str(v))]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: ObjectIdStr | None = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def to_mongo(self) -> dict[str, Any]:
        """Serialise for insertion. Drops `id` so Mongo assigns `_id` itself."""
        doc = self.model_dump(by_alias=True, exclude_none=True, mode="python")
        doc.pop("_id", None)
        return doc


# ── Identity ────────────────────────────────────────────────────────────────


class Role(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


class User(MongoModel):
    google_sub: str = Field(description="Google OIDC subject claim; the stable user key.")
    email: str
    name: str
    picture: str | None = None
    role: Role = Role.STUDENT
    instrument: str | None = None
    last_login_at: datetime = Field(default_factory=utcnow)


# ── Repertoire ──────────────────────────────────────────────────────────────


class Piece(MongoModel):
    """A single work a user is practising, plus its uploaded score."""

    owner_id: str
    title: str
    composer: str | None = None
    instrument: str | None = None
    # Where the uploaded PDF/image lives in object storage.
    score_key: str | None = None
    score_pages: int = 0
    tempo_bpm: int | None = None
    time_signature: str | None = None
    key_signature: str | None = None
    # Reference transcription, if we have one (MusicXML/MIDI-derived note list).
    reference_notes: list[NoteEvent] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Section(MongoModel):
    """A chunk of a piece: the unit a user actually drills.

    The chunking algorithm in the proposal produces these. Bar numbers are
    1-indexed and inclusive, matching how musicians talk about them.
    """

    piece_id: str
    owner_id: str
    index: int = Field(description="Order within the piece, 0-based.")
    label: str
    start_bar: int
    end_bar: int
    page: int = 1
    # Normalised crop box on the score page, for rendering just this chunk.
    bbox: tuple[float, float, float, float] | None = None
    difficulty: int = Field(default=3, ge=1, le=5)


# ── Practice ────────────────────────────────────────────────────────────────


class PracticeSession(MongoModel):
    user_id: str
    piece_id: str | None = None
    section_id: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: datetime | None = None
    duration_seconds: int = 0
    tempo_bpm: int | None = None
    notes: str | None = None
    recording_ids: list[str] = Field(default_factory=list)


class RecordingKind(str, Enum):
    """What the microphone captured, which decides how the worker treats it.

    A performance goes to the note transcriber; a spoken note goes to Whisper.
    Pointing speech-to-text at a piano gives nonsense and vice versa, so this
    has to be decided at record time, not guessed later.
    """

    PERFORMANCE = "performance"
    VOICE_NOTE = "voice_note"


class Recording(MongoModel):
    user_id: str
    session_id: str | None = None
    piece_id: str | None = None
    section_id: str | None = None
    kind: RecordingKind = RecordingKind.PERFORMANCE
    # Object-storage key. Bytes never pass through the API; the browser PUTs
    # straight to R2 with a presigned URL and the worker GETs it the same way.
    storage_key: str
    content_type: str = "audio/webm"
    size_bytes: int = 0
    duration_seconds: float | None = None
    status: Literal["pending", "uploaded", "analyzing", "analyzed", "failed"] = "pending"
    job_id: str | None = None
    feedback_id: str | None = None
    # Set for voice notes only: what Whisper heard.
    transcript: str | None = None


# ── Analysis ────────────────────────────────────────────────────────────────


class NoteEvent(BaseModel):
    """One detected or expected note. The lingua franca between ML and UI."""

    start: float = Field(description="Seconds from the start of the audio.")
    end: float
    midi: int = Field(ge=0, le=127)
    velocity: float = Field(default=0.8, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class NoteVerdict(str, Enum):
    CORRECT = "correct"
    WRONG_PITCH = "wrong_pitch"
    MISSED = "missed"
    EXTRA = "extra"
    LATE = "late"
    EARLY = "early"


class NoteComparison(BaseModel):
    index: int
    expected_midi: int | None = None
    played_midi: int | None = None
    timing_error_ms: float | None = None
    verdict: NoteVerdict


class Feedback(MongoModel):
    """What the ML worker produces and the coach reads."""

    user_id: str
    recording_id: str
    piece_id: str | None = None
    section_id: str | None = None

    pitch_accuracy: float = Field(ge=0.0, le=1.0)
    timing_accuracy: float = Field(ge=0.0, le=1.0)
    tempo_bpm_detected: float | None = None
    tempo_stability: float | None = Field(default=None, ge=0.0, le=1.0)
    dynamics_range_db: float | None = None

    notes_expected: int = 0
    notes_played: int = 0
    comparisons: list[NoteComparison] = Field(default_factory=list)
    # Bar numbers worth re-drilling, cheapest possible input to the coach.
    problem_bars: list[int] = Field(default_factory=list)
    summary: str = ""
    engine: str = Field(default="stub", description="Which analysis backend produced this.")
    engine_version: str = "0"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class AnalysisJob(MongoModel):
    """A unit of work on the queue. Mongo holds the truth; Redis holds the nudge."""

    user_id: str
    recording_id: str
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    feedback_id: str | None = None


# Piece references NoteEvent before it is defined; resolve the forward ref.
Piece.model_rebuild()
