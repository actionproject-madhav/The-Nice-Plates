# Setup

Ordered by what unblocks the most people soonest. **Steps 1–2 get the whole
stack running with no accounts at all** — do those first, sign up for things
later.

---

## 1. Local, with nothing configured

```bash
make install
make api     # :8000
make web     # :5173  (second terminal)
make seed    # a month of practice history
```

Open <http://localhost:5173> and click **Dev sign-in**. You are looking at the
real API, the real database and the real worker. `GET /health/ready` lists what
is and isn't wired up.

Needs a MongoDB on `localhost:27017`. On macOS:
`brew install mongodb-community && brew services start mongodb-community`.

## 2. Verify it end to end

```bash
make smoke
```

Signs in, creates a piece, chunks it, starts a session, uploads audio, waits for
the worker, reads the feedback back, checks the dashboard totals, and confirms
one user cannot read another's data. **Run this before every PR.** CI runs it too.

---

## 3. MongoDB Atlas

1. <https://cloud.mongodb.com> → build a free **M0** cluster.
2. **Database Access** → add a user, save the password.
3. **Network Access** → allow `0.0.0.0/0`. Render's free tier has no static
   egress IP, so an allowlist of specific addresses will not work.
4. **Connect → Drivers** → copy the connection string.

```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=nice_plates
```

Indexes apply themselves on API startup. Nothing to run by hand.

## 4. Google sign-in

<https://console.cloud.google.com> → APIs & Services → Credentials →
**Create credentials → OAuth client ID → Web application**.

**Authorized JavaScript origins** — every URL the app is served from:
```
http://localhost:5173
https://<your-project>.vercel.app
```

Leave **Authorized redirect URIs empty**. We use the Google Identity Services
ID-token flow, not the authorization-code flow, so there is no callback URL.

The same client ID goes in two places:
```
GOOGLE_CLIENT_ID=...apps.googleusercontent.com        # API, verifies the token
VITE_GOOGLE_CLIENT_ID=...apps.googleusercontent.com   # web, renders the button
```

Adding a new deployment URL later means adding it here too, or sign-in fails
with an origin mismatch.

## 5. Session secret

```bash
openssl rand -hex 32     # → JWT_SECRET
```

Render generates this itself via `render.yaml`. You only need it locally if you
want tokens to survive a restart.

## 6. Cloudflare R2

<https://dash.cloudflare.com> → R2 → **Create bucket** `nice-plates` →
**Manage R2 API Tokens** → **Object Read & Write**.

```
R2_ACCOUNT_ID=          R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=   R2_BUCKET=nice-plates
```

Until these are set, uploads go to `.localstorage/` and the API serves them
back. Everything downstream behaves identically.

## 7. The coach

<https://platform.openai.com> → API keys.

```
OPENAI_API_KEY=sk-...
COACH_MODEL=gpt-4o      # any model with function calling
```

Without it `/v1/coach/ask` returns 503 and the rest of the app is unaffected.

---

## Deploy

### API + queue → Render

**New → Blueprint → this repo.** `render.yaml` creates the web service and a
free Key Value instance, and prompts for the secrets it deliberately does not
read from git: `MONGODB_URI`, `GOOGLE_CLIENT_ID`, `OPENAI_API_KEY`, the three
R2 values, and `CORS_ORIGINS`.

Set `CORS_ORIGINS` to your Vercel URL once you have it. The API rejects browser
requests from origins it doesn't know.

Free instances sleep after 15 minutes idle; the first request afterwards takes
~50s. That is the free tier, not a bug — mention it in the demo or upgrade the
instance for presentation day.

### Frontend → Vercel

**Add New → Project →** this repo.

| Setting | Value |
|---|---|
| Root Directory | `web` |
| Framework Preset | Vite |
| Build / Output / Install | leave the overrides off |

Environment variables, Production **and** Preview:
```
VITE_API_BASE_URL=https://nice-plates-api.onrender.com
VITE_GOOGLE_CLIENT_ID=...apps.googleusercontent.com
```

`VITE_` variables are baked in at build time, so **changing one requires a
redeploy** — editing it in the dashboard alone does nothing.

### The three things that break first

1. **Vercel URL not in Google's authorized origins** → sign-in fails silently.
2. **Vercel URL not in `CORS_ORIGINS` on Render** → every request fails CORS.
3. **Atlas network access not `0.0.0.0/0`** → the API boots but `/health/ready`
   reports mongo down.

---

## Splitting the worker out

Free Render has no background worker type, so the API hosts the analysis loop
(`EMBEDDED_WORKER=true`). When audio analysis gets heavy:

1. Add a `type: worker` service running `python audio/worker.py` with the same
   `MONGODB_URI` and `REDIS_URL`.
2. Set `EMBEDDED_WORKER=false` on the API.

No code changes. Both processes claim jobs with the same guarded status update,
so they can run side by side during the switchover without double-processing.

## Turning on the real transcriber

```bash
pip install -r audio/requirements-ml.txt    # basic-pitch, librosa, ~500MB
```

`transcribe()` picks up `basic-pitch` automatically. Too heavy for Render's free
build, which is why it isn't in the default requirements.
