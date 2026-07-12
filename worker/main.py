#!/usr/bin/env python3
"""Queue worker: claim jobs from Postgres and run SRT/Korail poll loops.

Set WORKER_MODE=queue (default when DATABASE_URL is set) for multi-job mode.
Set WORKER_MODE=smoke to run the legacy single-env smoke job once.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import UUID

import requests

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worker.db import bump_attempts, claim_next_job, connect, ensure_schema, finish_job, get_job
from worker.runners_korail import run_korail_job
from worker.runners_srt import run_srt_job


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def notify_telegram(text: str) -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text[:3500]},
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover
        print(f"[{datetime.now():%H:%M:%S}] telegram error: {exc}")


def get_egress_ip() -> str:
    try:
        r = requests.get("https://api.ipify.org", timeout=10)
        r.raise_for_status()
        return r.text.strip() or "unknown"
    except Exception as exc:  # pragma: no cover
        return f"error:{type(exc).__name__}"


def maybe_start_health_server() -> None:
    port_raw = _env("PORT")
    if not port_raw:
        return
    try:
        port = int(port_raw)
    except ValueError:
        return

    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[{datetime.now():%H:%M:%S}] health listening on :{port}")


def run_one_job(job: dict) -> None:
    job_id = job["id"]
    carrier = job["carrier"]
    print(f"[{datetime.now():%H:%M:%S}] claimed {job_id} carrier={carrier}")

    def _log(msg: str) -> None:
        print(f"[{datetime.now():%H:%M:%S}] job={job_id} {msg}")

    with connect() as conn:
        bump_attempts(conn, job_id)

    try:
        if carrier == "srt":
            result = run_srt_job(job, notify=_log)
        elif carrier == "korail":
            result = run_korail_job(job, notify=_log)
        else:
            raise RuntimeError(f"unsupported carrier: {carrier}")

        # Re-check cancel before marking success
        with connect() as conn:
            latest = get_job(conn, job_id)
            if latest and latest["status"] == "canceled":
                print(f"[{datetime.now():%H:%M:%S}] job {job_id} canceled during run")
                return
            finish_job(conn, job_id, status="succeeded", result=result)

        notify_telegram(
            f"Job succeeded {job_id}\n{carrier} {job['dep']}->{job['arr']} "
            f"{job['travel_date']} {job['dep_time']}\n{result.get('message')}"
        )
        print(f"[{datetime.now():%H:%M:%S}] job {job_id} succeeded")
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"
        with connect() as conn:
            latest = get_job(conn, job_id)
            if latest and latest["status"] == "canceled":
                return
            finish_job(conn, job_id, status="failed", error=err)
        notify_telegram(f"Job failed {job_id}\n{err}")
        print(f"[{datetime.now():%H:%M:%S}] job {job_id} failed: {err}", file=sys.stderr)


def queue_loop() -> int:
    maybe_start_health_server()
    egress = get_egress_ip()
    print(f"[{datetime.now():%H:%M:%S}] queue worker start egress_ip={egress}")
    notify_telegram(f"Train queue worker online\negress_ip={egress}")

    with connect() as conn:
        ensure_schema(conn)

    idle_sleep = float(_env("QUEUE_IDLE_SLEEP", "1.5") or "1.5")
    while True:
        try:
            with connect() as conn:
                job = claim_next_job(conn)
            if not job:
                time.sleep(idle_sleep)
                continue
            run_one_job(job)
        except Exception as exc:
            print(
                f"[{datetime.now():%H:%M:%S}] queue loop error: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            time.sleep(3)
    return 0


def smoke_once() -> int:
    """Legacy single-shot env-driven smoke (no queue)."""
    # Keep compatibility by importing previous behavior inline.
    from worker import smoke

    return smoke.main()


def main() -> int:
    mode = (_env("WORKER_MODE") or "").lower()
    if not mode:
        mode = "queue" if _env("DATABASE_URL") else "smoke"
    if mode == "queue":
        return queue_loop()
    if mode == "smoke":
        return smoke_once()
    print(f"Unknown WORKER_MODE={mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
