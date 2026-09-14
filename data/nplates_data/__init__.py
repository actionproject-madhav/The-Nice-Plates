"""Shared domain layer for The Nice Plates.

Both `platform/` (the API) and `audio/` (the ML worker) depend on this package so
there is exactly one definition of every document shape and queue message. If the
two services ever disagree about a field name, it is a bug in one import, not a
silent runtime mismatch.
"""

from nplates_data.collections import Collections
from nplates_data.models import (
    AnalysisJob,
    Feedback,
    JobStatus,
    NoteEvent,
    Piece,
    PracticeSession,
    Recording,
    RecordingKind,
    Section,
    User,
)

__all__ = [
    "AnalysisJob",
    "Collections",
    "Feedback",
    "JobStatus",
    "NoteEvent",
    "Piece",
    "PracticeSession",
    "Recording",
    "RecordingKind",
    "Section",
    "User",
]
