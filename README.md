# train

Unified SRT/Korail tooling with a Railway job queue (API + worker) and a
closed Next.js web console (`web/`).

## Monorepo layout

```
api/      # Hono TypeScript job API (Railway)
worker/  # Python queue consumer (Railway)
web/     # Next.js App Router UI (local / Vercel-ready)
```

## Web console (`web/`)

Closed passcode gate (`GATE_PASSCODE`, default `chasehuh`, case-sensitive) unlocks
an httpOnly cookie validated on every `/api/jobs*` route handler. Browser never
sees `RAILWAY_API_KEY`; Next.js proxies to the Railway API with a server-side
Bearer token.

### Local setup

```bash
cd web
cp .env.example .env.local
# Fill RAILWAY_API_KEY from .env.railway-local (API_KEY)
# Optional: ALLOW_ENV_CREDS=true to omit credentials and use worker env fallbacks

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
| `GATE_SECRET` | HMAC secret for unlock cookie |
| `ALLOW_ENV_CREDS` | If `true`, blank UI credentials fall back to worker env |

### Flow

1. Enter passcode → unlock cookie
2. Submit watch/reserve job → `POST /api/jobs` → Railway `POST /v1/jobs`
3. Job list polls every 3s; cancel queued/running jobs from the UI

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
| `SRT_ID` | SRT login id (membership / email / phone) |
| `SRT_PW` | SRT password |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional but recommended) |
| `TELEGRAM_CHAT_ID` | Telegram chat id |

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

`carrier` may be `srt` or `korail`. If `credentials` is omitted, the worker
falls back to `SRT_*` / `KORAIL_*` env vars.

### Autoscaling
Railway has **vertical** autoscaling (CPU/RAM) but **no queue-based horizontal
autoscaler**. For family concurrent use we run a fixed worker replica count
(`us-east`). Jobs are claimed with `FOR UPDATE SKIP LOCKED`, so each replica
picks a different job safely.
