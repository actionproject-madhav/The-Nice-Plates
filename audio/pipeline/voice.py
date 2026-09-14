"""Spoken practice notes → text, via OpenAI Whisper.

This is the right job for speech-to-text: a musician saying "worked bars 12 to
16, left hand still rushing" after a run-through. It is emphatically *not* how
we detect notes — Whisper on a piano recording returns nonsense. Note detection
lives in transcribe.py.

Without an API key this degrades to an empty transcript rather than failing the
job, so a voice note still gets stored and can be re-transcribed later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Whisper's hard limit is 25MB; anything larger is rejected by the API.
MAX_BYTES = 25 * 1024 * 1024


@dataclass
class VoiceNote:
    text: str
    engine: str
    language: str | None = None


def transcribe_speech(audio_path: str, api_key: str, model: str = "whisper-1") -> VoiceNote:
    if not api_key:
        log.info("voice: no OpenAI key; storing the note without a transcript")
        return VoiceNote(text="", engine="unconfigured")

    from pathlib import Path

    size = Path(audio_path).stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"Voice note is {size // 1_048_576}MB; Whisper's limit is 25MB.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    with open(audio_path, "rb") as handle:
        result = client.audio.transcriptions.create(
            model=model,
            file=handle,
            # Nudges Whisper toward musical vocabulary it would otherwise
            # mangle — "bars", "legato", note names, tempo markings.
            prompt=(
                "A musician's practice note. May mention bar numbers, tempo in BPM, "
                "dynamics, and terms like legato, staccato, rubato, arpeggio, and "
                "note names such as C sharp or B flat."
            ),
            response_format="verbose_json",
        )

    return VoiceNote(
        text=(result.text or "").strip(),
        engine=model,
        language=getattr(result, "language", None),
    )
