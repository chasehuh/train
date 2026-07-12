# train

Unified SRT/Korail tooling, plus a Railway worker for SRT cloud-IP smoke tests.

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
