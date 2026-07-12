#!/usr/bin/env python3
"""Queue worker: claim jobs from Postgres and run SRT/Korail poll loops.

Set WORKER_MODE=queue (default when DATABASE_URL is set) for multi-job mode.
Set WORKER_MODE=smoke to run the legacy single-env smoke job once.

Queue mode runs up to WORKER_CONCURRENCY (default 3) jobs in parallel via
ThreadPoolExecutor on a single process/replica.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import UUID

import requests

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worker.db import bump_attempts, claim_next_job, connect, ensure_schema, finish_job, get_job
from worker.exceptions import JobCanceled
from worker.supervisor import install_sigterm_flag, parse_concurrency, run_queue_supervisor


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
    """Bind $PORT for health checks and rail login verification (option A)."""
    port_raw = _env("PORT")
    if not port_raw:
        return
    try:
        port = int(port_raw)
    except ValueError:
        return

    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/health", "/healthz"):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"ok\n")
                return
            self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path not in ("/rail/login", "/rail/search"):
                self._json(404, {"ok": False, "error": "not_found"})
                return

            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                length = 0
            raw = self.rfile.read(max(0, length)) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except Exception:
                self._json(400, {"ok": False, "error": "invalid_json"})
                return

            carrier = str(data.get("carrier") or "").strip().lower()
            user_id = str(data.get("id") or "")
            password = str(data.get("pw") or "")
            if carrier not in ("srt", "korail"):
                self._json(
                    400,
                    {
                        "ok": False,
                        "error": "validation_failed",
                        "message": "carrier must be srt or korail",
                    },
                )
                return

            if path == "/rail/search":
                from worker.rail_search import search_trains

                trains, err = search_trains(
                    carrier,  # type: ignore[arg-type]
                    user_id,
                    password,
                    str(data.get("dep") or ""),
                    str(data.get("arr") or ""),
                    str(data.get("date") or ""),
                    str(data.get("time") or "000000"),
                    available_only=bool(data.get("available_only", False)),
                )
                if err is not None:
                    self._json(
                        err.status,
                        {
                            "ok": False,
                            "error": err.error,
                            "message": err.message,
                            "carrier": carrier,
                        },
                    )
                    return
                self._json(
                    200,
                    {
                        "ok": True,
                        "carrier": carrier,
                        "dep": str(data.get("dep") or "").strip(),
                        "arr": str(data.get("arr") or "").strip(),
                        "date": str(data.get("date") or "").strip(),
                        "time": str(data.get("time") or "000000").strip() or "000000",
                        "trains": trains or [],
                    },
                )
                return

            from worker.rail_verify import verify_rail_login

            result = verify_rail_login(carrier, user_id, password)  # type: ignore[arg-type]
            if not result.ok:
                self._json(
                    401,
                    {
                        "ok": False,
                        "error": result.error or "login_failed",
                        "message": result.message or "login failed",
                        "carrier": result.carrier,
                        "id_masked": result.id_masked,
                    },
                )
                return

            from datetime import timezone

            verified_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            self._json(
                200,
                {
                    "ok": True,
                    "carrier": result.carrier,
                    "id_normalized": result.id_normalized,
                    "id_masked": result.id_masked,
                    "verified_at": verified_at,
                },
            )

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"[{datetime.now():%H:%M:%S}] health+verify listening on :{port}")


def make_cancel_check(job_id: UUID) -> Callable[[], bool]:
    """Return True when the job row is no longer ``running`` (canceled)."""

    def should_stop() -> bool:
        try:
            with connect() as conn:
                latest = get_job(conn, job_id)
            return bool(latest and latest["status"] == "canceled")
        except Exception as exc:  # pragma: no cover
            print(f"[{datetime.now():%H:%M:%S}] job={job_id} cancel check error: {exc}")
            return False

    return should_stop


def run_one_job(job: dict) -> None:
    job_id = job["id"]
    carrier = job["carrier"]
    print(f"[{datetime.now():%H:%M:%S}] claimed {job_id} carrier={carrier}")

    def _log(msg: str) -> None:
        print(f"[{datetime.now():%H:%M:%S}] job={job_id} {msg}")

    with connect() as conn:
        bump_attempts(conn, job_id)

    cancel_check = make_cancel_check(job_id)

    try:
        if carrier == "srt":
            from worker.runners_srt import run_srt_job

            result = run_srt_job(job, notify=_log, should_stop=cancel_check)
        elif carrier == "korail":
            from worker.runners_korail import run_korail_job

            result = run_korail_job(job, notify=_log, should_stop=cancel_check)
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
    except JobCanceled:
        print(f"[{datetime.now():%H:%M:%S}] job {job_id} canceled during poll")
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
    concurrency = parse_concurrency(_env("WORKER_CONCURRENCY", "3"))
    idle_sleep = float(_env("QUEUE_IDLE_SLEEP", "1.5") or "1.5")
    egress = get_egress_ip()
    print(
        f"[{datetime.now():%H:%M:%S}] queue worker start egress_ip={egress} "
        f"concurrency={concurrency}"
    )
    notify_telegram(
        f"Train queue worker online\negress_ip={egress}\nconcurrency={concurrency}"
    )

    with connect() as conn:
        ensure_schema(conn)

    stop = install_sigterm_flag()

    def claim_job() -> dict | None:
        with connect() as conn:
            return claim_next_job(conn)

    run_queue_supervisor(
        claim_job=claim_job,
        run_job=run_one_job,
        concurrency=concurrency,
        idle_sleep=idle_sleep,
        should_stop=stop,
    )
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
