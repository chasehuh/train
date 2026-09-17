# train

Personal **Korail** CLI. Search, poll, hold a seat, pay in 코레일+.

Since the **2026-09-01** high-speed integration, former SRT trains are booked on Korail as KTX / KTX-산천. The SRT client is gone.

This is not a product. One checkout, one `.env`, pay yourself before the hold expires.

## Seat choice

`--class special|general|any` is the grade. `--seat-letter A` is the column.

Korail letter path: residual seat map (`TrainResearch` + `ResidualSeatsResearch`) → specified-seat reserve. If the map is empty, auto-assign then `ReservationList` (`hidPnrNo`). Wrong letter → cancel and retry.

Holds are unpaid. Pay in 코레일+.

## Install

```bash
cd train
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Never commit `.env`. Korail membership IDs are digits.

## Commands

```bash
train doctor
train search --dep 수서 --arr 동대구 --date 20260918 --time 173000
train reservations

# map A first, else reserve+cancel; stop after 90 minutes
train watch --dep 수서 --arr 동대구 \
  --date 20260918 --time 173000 --end-time 183000 \
  --trains 347,351,349 --class special --seat-letter A --interval 3 --max-minutes 90

train reserve --dep 수서 --arr 동대구 --date 20260918 --time 173000 --trains 347 --class special
```

`--monitor-only` logs + Telegram without reserving. No `--trains` → first match at or after `--time`. `--max-minutes` exits with code 3 when the budget is spent.

## Web dashboard (train.chasehuh.com)

The same service also serves a mobile-first dashboard that clones the Korail app flow: 로그인 → 출발/도착/날짜/시각 조회 → 열차 선택 → 좌석 등급/위치 → 예약 시도 → 예약 내역/취소. Open `/`, log in with the Korail id + password, search, tap **예약 시도** on a train. Each attempt becomes a job on its own sandbox (same runner as `POST /jobs`), so the polling never runs in the web process. Holds are unpaid; pay in 코레일톡.

**Where the password lives, and for how long**

1. Browser form until submit (cleared right after).
2. Control-plane process memory only, inside the session's Korail client: idle TTL 30 min, absolute TTL 8 h, or until 로그아웃. Never on disk, in a database, in logs, in job records, or in the session cookie.
3. Create-time variables of each per-job sandbox VM, for that sandbox's life (`max_minutes` + 5 min grace at most, then destroyed).

**Browser security:** session id in an `HttpOnly; Secure; SameSite=Strict` cookie; every mutating `/web/*` call needs the `X-CSRF-Token` handed out at login; login is JSON-only and rate-limited (5 failures per 15 min per client IP and per Korail id, because Korail locks memberships after 5 bad passwords); CSP `default-src 'self'`, `X-Frame-Options: DENY`, `no-store` on API responses, no API docs endpoint.

## Railway per-job workers

Korail's mobile API is sensitive to repeated polls from one egress IP, so each watch job runs on its **own Railway sandbox** (a fresh VM with its own public IP, measured: three concurrent sandboxes → three distinct IPv4s). A tiny control plane creates one sandbox per `POST /jobs`, starts `train watch` there, and destroys the sandbox when the worker exits, is cancelled, or runs out of time.

```
POST /jobs ─► control plane (one Railway service, FastAPI)
                 │  sandboxCreate(template = checkpoint, variables = KORAIL_* / TELEGRAM_*)
                 │  sandboxExec("… setsid nohup python3 -m train watch … &")
                 ▼
             sandbox per job ── own public IP ── Telegram on start + kept hold ── exits after hold
                 ▲
                 └─ reaper polls /job/exit + tail, heartbeats, destroys on terminal status
```

### 1. Build the worker checkpoint

Workers boot from a checkpoint that already has this checkout installed (about 5 s to first command).

```bash
railway login
scripts/checkpoint.sh -p <project id> -e production      # prints WORKER_TEMPLATE=train-<sha>
```

Re-run after every change to `train/` or `korail2/`.

### 2. Deploy the control plane + web (one service)

One Railway service in project `train_chasehuh_com`, built from the `Dockerfile` (`railway up` from a checkout, or connect the GitHub repo). Service variables:

| Variable | Purpose |
|---|---|
| `JOB_API_TOKEN` | Bearer token for the scripted `/jobs` API |
| `RAILWAY_TOKEN`, `RAILWAY_ENVIRONMENT_ID` | Project token + environment where sandboxes are created |
| `WORKER_TEMPLATE` | Checkpoint name from step 1 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Forwarded into each sandbox (reference the old `worker` service: `${{worker.TELEGRAM_BOT_TOKEN}}`) |
| `KORAIL_ID`, `KORAIL_PW` | Only for the bearer `/jobs` path; the web dashboard uses the session's credentials instead |
| `WORKER_REGION` | Optional, e.g. `asia-southeast1-eqsg3a` |
| `WORKER_IDLE_TIMEOUT_MINUTES` | Backstop idle destroy, default 30 |

Secrets never travel in the job body; the API only accepts trip fields.

**Domain:** in the service's Settings → Networking add custom domain `train.chasehuh.com` (or `railway domain`). Railway prints a `CNAME` target and a `TXT` verification record; create both in Cloudflare (DNS for `chasehuh.com`), replacing the old Vercel `CNAME`. Railway issues the TLS certificate once both records verify. With the Cloudflare proxy on, set SSL/TLS mode to Full.

**Old services:** `api`, `worker`, `Postgres` in the same project are the retired SaaS. Keep `worker` only as the holder of `TELEGRAM_*` / `KORAIL_*` until they are moved to shared variables; the rest can be deleted.

### 3. Submit jobs

```bash
curl -s -X POST "$URL/jobs" -H "Authorization: Bearer $JOB_API_TOKEN" -H 'Content-Type: application/json' -d '{
  "dep": "수서", "arr": "동대구", "date": "20260918",
  "time": "173000", "end_time": "183000",
  "trains": ["347", "351"], "seat_class": "special", "seat_letter": "A",
  "interval_sec": 3, "monitor_only": false
}'
curl -s "$URL/jobs/job_1a2b3c4d" -H "Authorization: Bearer $JOB_API_TOKEN"   # status, egress_ip, log_tail
curl -s -X DELETE "$URL/jobs/job_1a2b3c4d" -H "Authorization: Bearer $JOB_API_TOKEN"
```

Statuses: `provisioning → running → reserved | idle_timeout | cancelled | failed`. Optional `max_minutes` (1..360) caps the worker; default is until departure + 15 min. The worker exits right after a kept hold so the box stops polling inside the pay window.

## Notes

- Tight 청도 last-mile is a **second** Korail ticket (ITX / 무궁화).
- Telegram fires on watch start and on a kept hold. Pay window can be ~10 minutes.
- Korail login needs the in-repo antibot helper.
- Upstream: [carpedm20/korail2](https://github.com/carpedm20/korail2), [bsangmin/letskorail](https://github.com/bsangmin/letskorail) seat-map endpoints.
- Sandboxes are billed per second while running; every job has an idle timeout, a deadline, and destroy-on-done.

```
train/          CLI, job spec, watch loop
train/server/   control plane (FastAPI + Railway GraphQL client + job reaper)
korail2/        Korail mobile API (antibot, residual seats, holds)
scripts/        worker checkpoint build
tests/          unit tests (no live Korail)
```
