# train

Unified SRT/Korail tooling with a Railway job queue (API + worker) and a
closed Next.js web console (`web/`).

## Monorepo layout

```
api/      # Hono TypeScript job API (Railway)
worker/  # Python queue consumer (Railway)
web/     # Next.js App Router UI (local / Vercel-ready)
```

## Auth model (two layers)

Site access and rail accounts are **different**:

1. **Site gate** — shared passcode (`GATE_PASSCODE`, default `chasehuh`) sets
   httpOnly `train_gate`. This only unlocks the closed console UI.
2. **Rail login** — each user selects SRT or Korail (KTX), enters membership /
   phone / email + password. The API asks the worker to verify against the real
   carrier login. On success, Next sets httpOnly encrypted `train_rail` (12h TTL)
   with `{ carrier, id, pw, verifiedAt }`.

Jobs inherit the rail session: the web proxy injects `credentials` and forces
`carrier` from the session. Workers require `credentials_enc` on queue jobs by
default (`ALLOW_ENV_CREDS=true` or `WORKER_MODE=smoke` only for env fallbacks).

## Web console (`web/`)

Browser never sees `RAILWAY_API_KEY`; Next.js proxies to the Railway API with a
server-side Bearer token. `/api/jobs*` and `/api/rail/*` require the site gate.

### Local setup

```bash
cd web
cp .env.example .env.local
# Fill RAILWAY_API_KEY from .env.railway-local (API_KEY)
# APP_SECRET / GATE_SECRET encrypt the rail session cookie

pnpm install
pnpm dev
# open http://localhost:3000
```

### Env vars

| Variable | Purpose |
|---|---|
| `RAILWAY_API_URL` | Railway API base URL |
| `RAILWAY_API_KEY` | Bearer token for `/v1/*` (server-only) |
| `GATE_PASSCODE` | Landing unlock code (case-sensitive) |
| `GATE_SECRET` | HMAC secret for site unlock cookie |
| `APP_SECRET` | Prefer for rail session cookie encryption (falls back to `GATE_SECRET`) |
| `ALLOW_ENV_CREDS` | Dev/smoke only: allow jobs without a rail session (default off) |
| `TRAIN_SEARCH_MOCK` | Web: `true` force mock trains; `false` live-only; unset = live with mock fallback |

### Flow

1. Enter site passcode → `train_gate` cookie
2. Enter SRT/Korail credentials → verify via API/worker → `train_rail` cookie
3. **Browse** trains (SRT-style search bar → Korail-style results) via
   `POST /api/trains/search` (proxies `POST /v1/trains/search`)
4. Select a train + seat class → **Confirm** creates an exact-time watch job
   (`POST /api/jobs`) with session credentials; `dry_run` defaults on
5. Watches tab polls every 3s; **Rail logout** clears rail session; **Lock site**
   clears gate only

If Railway has not yet deployed the search endpoint, the web proxy falls back to
mock timetable fixtures (set `TRAIN_SEARCH_MOCK=true` to force, or
`TRAIN_SEARCH_MOCK=false` to disable fallback).

Vercel: `web/vercel.json` is a minimal Next.js hint. Deploy the `web/`
directory and set the env vars above in the Vercel project.

<!-- TODO: Google OAuth for multi-user identity (out of scope). -->


## Railway SRT smoke worker

The `worker` service runs the same poll/reserve loop as the local
`srt/scripts/srt_poll_reserve.py` script, using the vendored `src/srt_backend`
client (not PyPI `srtrain`, for reliability).

### Start command

```bash
python -m worker.main
```

Configured in `railway.toml` / `Dockerfile` (`CMD`).

### Required Railway env vars

| Variable | Purpose |
|---|---|
| `SRT_ID` / `SRT_PW` | Smoke / `ALLOW_ENV_CREDS` only — not used for normal queue jobs |
| `KORAIL_ID` / `KORAIL_PW` | Same as above for Korail smoke |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional but recommended) |
| `TELEGRAM_CHAT_ID` | Telegram chat id |
| `PORT` | Health + `POST /rail/login` verify server |
| `ALLOW_ENV_CREDS` | If `true`, queue runners may fall back to env credentials |

### Smoke job env vars

| Variable | Default | Purpose |
|---|---|---|
| `SMOKE_DEP` | `동대구` | Departure station |
| `SMOKE_ARR` | `수서` | Arrival station |
| `SMOKE_DATE` | today (`YYYYMMDD`) | Travel date |
| `SMOKE_TIME` | `220800` | Exact departure `HHMMSS` |
| `SMOKE_TARGET` | `1` | Number of 1-seat reservations |
| `SMOKE_CAR` | `4` | Keep only this car; cancel/retry otherwise (`any` to disable) |
| `SMOKE_INTERVAL` | `3` | Poll interval seconds |
| `SMOKE_DRY_RUN` | `true` | If true: login/search/poll only, then exit 0 |
| `SMOKE_MAX_ATTEMPTS` | `5` | Dry-run attempt cap (ignored when `SMOKE_DRY_RUN=false`) |

On start the worker prints the public egress IP (`https://api.ipify.org`) and
sends a Telegram message with that IP so you can confirm the Railway cloud IP.

### Flip dry-run for a real reserve test

1. First deploy with `SMOKE_DRY_RUN=true` (default) to verify login + search + egress IP.
2. For a real reservation: set `SMOKE_DRY_RUN=false` (and keep/adjust
   `SMOKE_DEP` / `SMOKE_ARR` / `SMOKE_DATE` / `SMOKE_TIME` / `SMOKE_CAR` /
   `SMOKE_TARGET`). The worker then reserves like the local poll script,
   including car-filter cancel/retry.

### Run locally

```bash
cd /path/to/train
python -m venv .venv && source .venv/bin/activate
pip install -e .
# or: pip install requests

cp .env.example .env   # fill SRT_ID / SRT_PW / Telegram
export PYTHONPATH=src

# Dry-run smoke (exits after SMOKE_MAX_ATTEMPTS)
SMOKE_DRY_RUN=true SMOKE_MAX_ATTEMPTS=3 python -m worker.main

# Real reserve (same semantics as srt_poll_reserve.py)
SMOKE_DRY_RUN=false python -m worker.main
```

Never commit `.env` or real SRT passwords.


## Queue API (multi-user)

TypeScript Hono API (`api/`) enqueues jobs into Postgres. Python `worker`
claims them with `FOR UPDATE SKIP LOCKED` so multiple jobs can sit in the
queue and workers drain them safely.

### Closed access
All `/v1/*` routes require `Authorization: Bearer $API_KEY`.

### Rail login verify
```bash
curl -sS -X POST "$API_URL/v1/rail/login" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"carrier":"srt","id":"YOUR_ID","pw":"YOUR_PW"}'
```

API forwards to the worker health server (`WORKER_VERIFY_URL`, e.g.
`http://${{worker.RAILWAY_PRIVATE_DOMAIN}}:$PORT`) at `POST /rail/login`.
Korail membership ids like `075-232-8289` are normalized to digits-only before login.

### Search trains
```bash
curl -sS -X POST "$API_URL/v1/trains/search" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "carrier": "srt",
    "dep": "수서",
    "arr": "대전",
    "date": "20260718",
    "time": "000000",
    "credentials": {"id": "YOUR_SRT_ID", "pw": "YOUR_SRT_PW"}
  }'
```

API forwards to worker `POST /rail/search` (same `WORKER_VERIFY_URL`). Requires
API + worker deploy for live results; the web console can fall back to fixtures.

### Create a job
```bash
curl -sS -X POST "$API_URL/v1/jobs" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "carrier": "srt",
    "dep": "동대구",
    "arr": "수서",
    "date": "20260712",
    "time": "220800",
    "target": 1,
    "car": 4,
    "dry_run": true,
    "max_attempts": 5,
    "credentials": {"id": "YOUR_SRT_ID", "pw": "YOUR_SRT_PW"}
  }'
```

`carrier` may be `srt` or `korail`. `credentials` is **required** unless
`ALLOW_ENV_CREDS=true` on the API (dev/smoke). The web console always injects
credentials from the verified rail session.

### API env extras

| Variable | Purpose |
|---|---|
| `WORKER_VERIFY_URL` | Base URL of worker verify/search HTTP (no trailing path) |
| `WORKER_VERIFY_TIMEOUT_MS` | Login verify timeout (default 15000) |
| `WORKER_SEARCH_TIMEOUT_MS` | Train search timeout (default 30000) |
| `ALLOW_ENV_CREDS` | Allow job create without `credentials` (default false) |

### Worker concurrency (not multi-replica)

Railway has **vertical** autoscaling (CPU/RAM) but **no queue-based horizontal
autoscaler / HPA**. Keep the worker at **1 replica** (Serverless/App Sleep OFF)
and raise in-process concurrency instead:

| Variable | Default | Purpose |
|---|---|---|
| `WORKER_CONCURRENCY` | `3` | Max simultaneous poll jobs in one worker process (min 1, soft-cap 8) |
| `QUEUE_IDLE_SLEEP` | `1.5` | Sleep seconds when no claimable jobs or all slots are full |

Mental model: **1 replica + concurrency N ≈ N terminals** on one machine.
With the default `WORKER_CONCURRENCY=3`, up to three SRT/Korail poll loops run
in parallel via `ThreadPoolExecutor`. Jobs are still claimed with
`FOR UPDATE SKIP LOCKED`, so threads never take the same row.

`WORKER_CONCURRENCY=1` restores the previous serial behavior.
