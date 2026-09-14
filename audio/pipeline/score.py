"""Turning a comparison into feedback a person can act on."""

from __future__ import annotations

import statistics
from collections import Counter

from nplates_data.models import Feedback, NoteComparison, NoteEvent, NoteVerdict


def estimate_tempo(notes: list[NoteEvent]) -> tuple[float | None, float | None]:
    """(bpm, stability 0-1) from the median gap between note onsets."""
    if len(notes) < 4:
        return None, None

    gaps = [b.start - a.start for a, b in zip(notes, notes[1:]) if b.start > a.start]
    if not gaps:
        return None, None

    median_gap = statistics.median(gaps)
    if median_gap <= 0:
        return None, None

    bpm = 60.0 / median_gap
    # Stability is 1 minus the coefficient of variation: even gaps, steady player.
    spread = statistics.pstdev(gaps) / median_gap if len(gaps) > 1 else 0.0
    return round(bpm, 1), round(max(0.0, 1.0 - spread), 3)


def bars_from_note_index(index: int, notes_per_bar: int = 4, first_bar: int = 1) -> int:
    return first_bar + index // max(notes_per_bar, 1)


def score(
    user_id: str,
    recording_id: str,
    comparisons: list[NoteComparison],
    played: list[NoteEvent],
    expected: list[NoteEvent],
    *,
    piece_id: str | None = None,
    section_id: str | None = None,
    first_bar: int = 1,
    engine: str = "stub",
    engine_version: str = "1",
) -> Feedback:
    counts = Counter(c.verdict for c in comparisons)
    total = len(comparisons) or 1

    # Pitch: a note counts if the right pitch was played at all, whenever.
    right_pitch = counts[NoteVerdict.CORRECT] + counts[NoteVerdict.LATE] + counts[NoteVerdict.EARLY]
    pitch_accuracy = right_pitch / total

    # Timing: judged only over the notes that were pitched correctly, so a
    # wrong note isn't punished twice.
    timed = right_pitch or 1
    timing_accuracy = counts[NoteVerdict.CORRECT] / timed

    tempo_bpm, tempo_stability = estimate_tempo(played)

    problem_bars = sorted(
        {
            bars_from_note_index(c.index, first_bar=first_bar)
            for c in comparisons
            if c.verdict is not NoteVerdict.CORRECT
        }
    )

    return Feedback(
        user_id=user_id,
        recording_id=recording_id,
        piece_id=piece_id,
        section_id=section_id,
        pitch_accuracy=round(pitch_accuracy, 4),
        timing_accuracy=round(timing_accuracy, 4),
        tempo_bpm_detected=tempo_bpm,
        tempo_stability=tempo_stability,
        notes_expected=len(expected),
        notes_played=len(played),
        comparisons=comparisons[:500],
        problem_bars=problem_bars[:24],
        summary=_summarize(counts, pitch_accuracy, timing_accuracy, tempo_bpm, problem_bars),
        engine=engine,
        engine_version=engine_version,
    )


def _summarize(
    counts: Counter,
    pitch: float,
    timing: float,
    tempo: float | None,
    problem_bars: list[int],
) -> str:
    """One plain sentence. The coach elaborates; this just states the facts."""
    parts = [f"{pitch:.0%} of notes at the right pitch, {timing:.0%} in time"]
    if tempo:
        parts.append(f"around {tempo:.0f} bpm")
    if counts[NoteVerdict.MISSED]:
        parts.append(f"{counts[NoteVerdict.MISSED]} notes missed")
    if counts[NoteVerdict.EXTRA]:
        parts.append(f"{counts[NoteVerdict.EXTRA]} extra notes")
    if problem_bars:
        shown = ", ".join(str(b) for b in problem_bars[:5])
        parts.append(f"roughest around bar{'s' if len(problem_bars) > 1 else ''} {shown}")
    return "; ".join(parts) + "."
