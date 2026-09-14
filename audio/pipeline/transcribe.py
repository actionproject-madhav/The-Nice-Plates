"""Audio → notes.

Two engines behind one function. `basic-pitch` (Spotify's polyphonic
transcriber) when it is installed; a deterministic stub when it is not, so the
whole pipeline — queue, storage, scoring, dashboard — can be built and demoed
before anyone waits on a 500MB TensorFlow install.

`transcribe()` returns the same shape either way, and `engine` says which ran.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from nplates_data.models import NoteEvent

log = logging.getLogger(__name__)


@dataclass
class Transcription:
    notes: list[NoteEvent]
    duration_seconds: float
    engine: str
    engine_version: str


def _basic_pitch_available() -> bool:
    try:
        import basic_pitch  # noqa: F401

        return True
    except ImportError:
        return False


def _transcribe_basic_pitch(audio_path: str) -> Transcription:
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import predict

    _, _, note_events = predict(audio_path, ICASSP_2022_MODEL_PATH)

    notes = [
        NoteEvent(
            start=float(start),
            end=float(end),
            midi=int(pitch),
            velocity=min(max(float(amplitude), 0.0), 1.0),
            confidence=min(max(float(amplitude), 0.0), 1.0),
        )
        for start, end, pitch, amplitude, *_ in note_events
    ]
    notes.sort(key=lambda n: n.start)
    duration = max((n.end for n in notes), default=0.0)
    return Transcription(notes, duration, "basic-pitch", "0.4.0")


def _transcribe_stub(audio_path: str) -> Transcription:
    """A believable C-major scale, seeded by the file's bytes.

    Deterministic on purpose: the same upload produces the same "performance"
    every time, so a failing test is a real regression rather than noise.
    """
    with open(audio_path, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()

    scale = [60, 62, 64, 65, 67, 69, 71, 72]
    notes: list[NoteEvent] = []
    t = 0.0
    for i in range(16):
        b = digest[i % len(digest)]
        midi = scale[i % len(scale)] + (12 if b > 200 else 0)
        dur = 0.35 + (b % 5) * 0.05
        notes.append(
            NoteEvent(
                start=round(t, 3),
                end=round(t + dur, 3),
                midi=midi,
                velocity=round(0.55 + (b % 40) / 100, 3),
                confidence=round(0.7 + (b % 25) / 100, 3),
            )
        )
        t += dur
    return Transcription(notes, round(t, 3), "stub", "1")


def transcribe(audio_path: str) -> Transcription:
    if _basic_pitch_available():
        try:
            return _transcribe_basic_pitch(audio_path)
        except Exception as exc:
            log.warning("basic-pitch failed (%s); falling back to the stub engine", exc)
    return _transcribe_stub(audio_path)
