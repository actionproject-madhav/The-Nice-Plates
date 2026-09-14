# The Nice Plates

A practice log for musicians. Record a take, and get back the bars you rushed,
the notes you missed, and the tempo you actually held.

CS Capstone — Robert, Ava, Madhav, Zachary.

---

## Run it

Needs Python 3.11+, Node 20+, and a MongoDB you can reach.

```bash
make install     # venv + pip + npm
make api         # API on :8000, worker in-process
make web         # frontend on :5173  (second terminal)
make smoke       # end-to-end test of the whole pipeline
```

**It runs with an empty `.env`.** No Mongo Atlas, no R2, no Google, no OpenAI
key required to get the whole loop working locally:

| Missing | What happens instead |
|---|---|
| `REDIS_URL` | the worker falls back to a 30s Mongo sweep |
| R2 credentials | uploads go to `.localstorage/` and the API serves them |
| `GOOGLE_CLIENT_ID` | use `POST /v1/auth/dev-login` (refuses to run in production) |
| `OPENAI_API_KEY` | the coach returns 503; everything else works |
| `basic-pitch` | a deterministic stub transcriber stands in |

`GET /health/ready` names every dependency and whether it is actually wired up.

## Layout

```
web/        React + Vite + TypeScript      → Vercel
platform/   FastAPI                        → Render
audio/      ML worker (transcribe · DTW · score)
data/       Shared models, collections, indexes  (both services import this)
scripts/    smoke test, seed
```

`data/` is installed into both Python services (`pip install -e ./data`), so
the API and the worker cannot disagree about a document shape.

## How a take becomes feedback

```
browser                 API                  storage        worker           Mongo
  │  POST upload-url     │                      │             │                │
  │─────────────────────>│  create recording ───┼─────────────┼───────────────>│
  │<── presigned PUT ────│                      │             │                │
  │  PUT bytes ──────────┼─────────────────────>│             │                │
  │  POST complete ─────>│  enqueue job ────────┼────────────>│                │
  │                      │                      │<── GET ─────│                │
  │                      │                      │             │ transcribe     │
  │                      │                      │             │ align (DTW)    │
  │                      │                      │             │ score ────────>│
  │  GET recording ─────>│<─────────────────────┼─────────────┼── feedback ────│
```

Audio never passes through the API. The browser PUTs straight to storage and
the worker GETs from it, which is what keeps a free 512MB instance viable.

## Decisions worth knowing

**FastAPI, not Flask.** The proposal said Flask; the architecture diagram said
FastAPI, and FastAPI is right here — async Mongo without a thread pool, request
validation shared with the worker via Pydantic, and `/docs` generated from the
code so the team has a live API reference.

**The worker runs in-process by default.** Render's free tier has no background
worker type. `EMBEDDED_WORKER=true` runs the analysis loop inside the API's
event loop; `audio/worker.py` is the same code standalone. Splitting them is a
one-env-var change, not a rewrite.

**Redis is an optimisation, not a dependency.** Mongo holds job state; Redis
only carries the nudge. A wiped free-tier Redis costs latency, not work.

**Every coach tool is read-only and scoped to one `user_id`,** bound server-side
from the JWT. A prompt can ask for someone else's data; the query can't express
it.

## Deploy

- **Frontend → Vercel.** Root directory `web`, preset Vite. Set
  `VITE_API_BASE_URL` and `VITE_GOOGLE_CLIENT_ID`.
- **API + queue → Render.** New → Blueprint → this repo. `render.yaml` creates
  both and prompts for the secrets it won't read from git.
- **Database → MongoDB Atlas M0.** Network access must allow `0.0.0.0/0`;
  Render's free tier has no static egress IP.

Set the deployed Vercel URL as an authorized JavaScript origin on the Google
OAuth client, and add it to `CORS_ORIGINS` on Render. Sign-in fails without both.

See `docs/SETUP.md` for the full walkthrough.
