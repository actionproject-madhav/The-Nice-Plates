# Data model

Eight collections. Every document shape is defined once in
`data/nplates_data/models.py` and imported by both the API and the worker, so
the two services cannot drift.

```
users ──┬── pieces ──── sections
        │     │
        │     └── practice_sessions ──── recordings ──── feedback
        │                                    │
        │                                    └── analysis_jobs
        └── coach_threads
```

| Collection | Holds | Key indexes |
|---|---|---|
| `users` | identity from Google | `google_sub` unique, `email` unique |
| `pieces` | a work, its score key, its reference transcription | `owner_id + updated_at` |
| `sections` | a chunk of bars — the unit people drill | `piece_id + index` |
| `practice_sessions` | the timer around a practice run | `user_id + started_at` |
| `recordings` | one take: storage key, status, job link | `storage_key` unique |
| `feedback` | what the worker concluded about a take | `recording_id` unique |
| `analysis_jobs` | queue state; the source of truth, not Redis | `status + created_at` |
| `coach_threads` | conversation transcripts | `user_id + updated_at` |

## Decisions

**`google_sub`, not email, is the user key.** Emails get reassigned; Google's
subject claim doesn't.

**`feedback.recording_id` is unique.** A retried job replaces its verdict rather
than stacking a second one, so the accuracy trend can't be polluted by retries.

**Jobs live in Mongo; Redis only carries the nudge.** A wiped free-tier Redis
costs latency, not work — the worker's 30-second sweep finds anything still
`queued`.

**Sections store bar numbers, not audio offsets.** Musicians talk in bars, the
UI labels in bars, and the coach reports problems in bars. One vocabulary from
the score to the feedback.

**Reference notes hang off the piece, not the section.** A section is a bar
range into the same performance, so storing one transcription per piece avoids
duplicating and re-syncing it per chunk.

## Scaling notes

M0 is 512MB and 500 connections. What actually grows:

- **`feedback.comparisons`** is capped at 500 note comparisons per document. An
  uncapped list on a long movement is the one field that could blow the 16MB
  document limit.
- **Audio never enters Mongo.** Only the storage key does.
- **Connection pools are capped** (API 20, worker 5) so the two services plus
  Atlas's own overhead stay well inside 500.

The first thing to shard if this ever needs it is `feedback`, by `user_id`.
