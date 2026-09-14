"""Canonical MongoDB collection names.

Import these instead of typing string literals; a typo in a collection name
creates a new empty collection rather than raising, which is a miserable bug.
"""

from typing import Final


class Collections:
    USERS: Final = "users"
    PIECES: Final = "pieces"
    SECTIONS: Final = "sections"
    SESSIONS: Final = "practice_sessions"
    RECORDINGS: Final = "recordings"
    FEEDBACK: Final = "feedback"
    JOBS: Final = "analysis_jobs"
    COACH_THREADS: Final = "coach_threads"

    ALL: Final = (
        USERS,
        PIECES,
        SECTIONS,
        SESSIONS,
        RECORDINGS,
        FEEDBACK,
        JOBS,
        COACH_THREADS,
    )
