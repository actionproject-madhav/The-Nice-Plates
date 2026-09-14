"""Aligning what was played against what was written.

Dynamic time warping over pitch sequences. DTW is the right tool because a
musician who plays every note correctly but 15% slow should score as correct —
a naive index-by-index comparison would call that a total failure.

Pure Python and O(n*m). Fine for a section of a few hundred notes; if we ever
align a whole movement, swap the inner loop for numpy.
"""

from __future__ import annotations

from nplates_data.models import NoteComparison, NoteEvent, NoteVerdict

# A note landing more than this far from where it belongs reads as early/late
# to an audience, not as expressive timing.
TIMING_TOLERANCE_MS = 120.0


def _cost(expected: NoteEvent, played: NoteEvent) -> float:
    """Pitch distance in semitones; an octave error is still a wrong note."""
    return abs(expected.midi - played.midi)


def dtw_align(
    expected: list[NoteEvent], played: list[NoteEvent]
) -> list[tuple[int | None, int | None]]:
    """Return (expected_index, played_index) pairs; None means unmatched."""
    if not expected:
        return [(None, j) for j in range(len(played))]
    if not played:
        return [(i, None) for i in range(len(expected))]

    n, m = len(expected), len(played)
    inf = float("inf")
    d = [[inf] * (m + 1) for _ in range(n + 1)]
    d[0][0] = 0.0

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = _cost(expected[i - 1], played[j - 1])
            d[i][j] = c + min(
                d[i - 1][j - 1],  # match
                d[i - 1][j] + 1.0,  # a written note went unplayed
                d[i][j - 1] + 1.0,  # an extra note appeared
            )

    path: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i == 0:
            path.append((None, j - 1))
            j -= 1
        elif j == 0:
            path.append((i - 1, None))
            i -= 1
        else:
            diag, up, left = d[i - 1][j - 1], d[i - 1][j], d[i][j - 1]
            best = min(diag, up, left)
            if best == diag:
                path.append((i - 1, j - 1))
                i, j = i - 1, j - 1
            elif best == up:
                path.append((i - 1, None))
                i -= 1
            else:
                path.append((None, j - 1))
                j -= 1
    path.reverse()
    return path


def compare(expected: list[NoteEvent], played: list[NoteEvent]) -> list[NoteComparison]:
    comparisons: list[NoteComparison] = []

    # Tempo-normalise before judging timing: play the right notes at 90% speed
    # and every note is "late" unless we scale first.
    scale = 1.0
    if expected and played:
        exp_span = expected[-1].end - expected[0].start
        play_span = played[-1].end - played[0].start
        if exp_span > 0 and play_span > 0:
            scale = exp_span / play_span

    for idx, (ei, pj) in enumerate(dtw_align(expected, played)):
        if ei is None and pj is not None:
            comparisons.append(
                NoteComparison(
                    index=idx, played_midi=played[pj].midi, verdict=NoteVerdict.EXTRA
                )
            )
            continue
        if pj is None and ei is not None:
            comparisons.append(
                NoteComparison(
                    index=idx, expected_midi=expected[ei].midi, verdict=NoteVerdict.MISSED
                )
            )
            continue
        if ei is None or pj is None:
            continue

        e, p = expected[ei], played[pj]
        if e.midi != p.midi:
            verdict = NoteVerdict.WRONG_PITCH
            error_ms = None
        else:
            error_ms = ((p.start - played[0].start) * scale - (e.start - expected[0].start)) * 1000
            if error_ms > TIMING_TOLERANCE_MS:
                verdict = NoteVerdict.LATE
            elif error_ms < -TIMING_TOLERANCE_MS:
                verdict = NoteVerdict.EARLY
            else:
                verdict = NoteVerdict.CORRECT

        comparisons.append(
            NoteComparison(
                index=idx,
                expected_midi=e.midi,
                played_midi=p.midi,
                timing_error_ms=round(error_ms, 1) if error_ms is not None else None,
                verdict=verdict,
            )
        )
    return comparisons
