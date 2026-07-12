#!/usr/bin/env python3
"""Legacy single-env SRT smoke runner (WORKER_MODE=smoke)."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Vendored SRT client lives under src/
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from srt_backend import SRT, SeatType
from srt_backend.passenger import Adult


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    return float(raw)


def load_env_file() -> None:
    """Load repo-root .env into os.environ without overriding existing keys."""
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_egress_ip() -> str:
    try:
        response = requests.get("https://api.ipify.org", timeout=10)
        response.raise_for_status()
        return response.text.strip() or "unknown"
    except Exception as exc:  # pragma: no cover
        return f"error:{type(exc).__name__}"


def notify_telegram(token: str | None, chat_id: str | None, text: str) -> None:
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            print(
                f"[{datetime.now():%H:%M:%S}] telegram failed: "
                f"{response.status_code} {response.text[:200]}"
            )
    except Exception as exc:  # pragma: no cover
        print(f"[{datetime.now():%H:%M:%S}] telegram error: {exc}")


def maybe_start_health_server() -> None:
    """Optional tiny HTTP health listener if Railway injects PORT."""
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[{datetime.now():%H:%M:%S}] health listening on :{port}")


def main() -> int:
    load_env_file()
    maybe_start_health_server()

    srt_id = _env("SRT_ID")
    srt_pw = _env("SRT_PW")
    telegram_token = _env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = _env("TELEGRAM_CHAT_ID")

    dep = _env("SMOKE_DEP", "동대구") or "동대구"
    arr = _env("SMOKE_ARR", "수서") or "수서"
    dep_date = _env("SMOKE_DATE", datetime.now().strftime("%Y%m%d")) or datetime.now().strftime(
        "%Y%m%d"
    )
    exact_time = _env("SMOKE_TIME", "220800") or "220800"
    target = _env_int("SMOKE_TARGET", 1)
    car_raw = _env("SMOKE_CAR", "4")
    car_filter = str(int(car_raw)) if car_raw not in (None, "", "any", "ANY") else None
    interval = _env_float("SMOKE_INTERVAL", 3.0)
    dry_run = _env_bool("SMOKE_DRY_RUN", True)
    max_attempts = _env_int("SMOKE_MAX_ATTEMPTS", 5)

    # Normalize formats
    dep_date = datetime.strptime(dep_date, "%Y%m%d").strftime("%Y%m%d")
    exact_time = datetime.strptime(exact_time, "%H%M%S").strftime("%H%M%S")

    if not srt_id or not srt_pw:
        print("SRT_ID and SRT_PW are required", file=sys.stderr)
        return 1

    egress_ip = get_egress_ip()
    telegram_on = bool(telegram_token and telegram_chat_id)

    start_msg = (
        f"SRT smoke start\n"
        f"{dep}->{arr} date={dep_date} time={exact_time}\n"
        f"target={target} car={car_filter or 'any'} interval={interval}s\n"
        f"dry_run={dry_run} max_attempts={max_attempts}\n"
        f"egress_ip={egress_ip}"
    )
    print(f"[{datetime.now():%H:%M:%S}] {start_msg.replace(chr(10), ' | ')}")
    print(f"[{datetime.now():%H:%M:%S}] public egress IP: {egress_ip}")
    notify_telegram(telegram_token, telegram_chat_id, start_msg)

    try:
        srt = SRT(srt_id, srt_pw, verbose=False)
        print(f"[{datetime.now():%H:%M:%S}] login ok")
    except Exception as exc:
        err = f"SRT smoke login failed: {type(exc).__name__}: {exc}\negress_ip={egress_ip}"
        print(f"[{datetime.now():%H:%M:%S}] {err}", file=sys.stderr)
        notify_telegram(telegram_token, telegram_chat_id, err)
        return 1

    success = []
    attempt = 0

    try:
        while len(success) < target:
            attempt += 1
            if dry_run and attempt > max_attempts:
                done = (
                    f"SRT smoke dry-run finished after {max_attempts} attempts "
                    f"({dep}->{arr} {exact_time}) egress_ip={egress_ip}"
                )
                print(f"[{datetime.now():%H:%M:%S}] {done}")
                notify_telegram(telegram_token, telegram_chat_id, done)
                return 0

            try:
                trains = srt.search_train(
                    dep,
                    arr,
                    dep_date,
                    exact_time,
                    time_limit=exact_time,
                    available_only=True,
                )
                train = next((t for t in trains if t.dep_time == exact_time), None)
            except Exception as exc:
                print(
                    f"[{datetime.now():%H:%M:%S}] #{attempt} search error: "
                    f"{type(exc).__name__}: {exc}"
                )
                time.sleep(interval)
                continue

            if not train:
                print(f"[{datetime.now():%H:%M:%S}] #{attempt} no available seat")
                time.sleep(interval)
                continue

            print(f"[{datetime.now():%H:%M:%S}] #{attempt} candidate {train}")

            if dry_run:
                time.sleep(interval)
                continue

            try:
                reservation = srt.reserve(
                    train,
                    passengers=[Adult(1)],
                    special_seat=SeatType.GENERAL_ONLY,
                )
            except Exception as exc:
                print(
                    f"[{datetime.now():%H:%M:%S}] #{attempt} reserve failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                time.sleep(interval)
                continue

            ticket_lines = "\n".join(f"  - {ticket}" for ticket in reservation.tickets)
            print(f"[{datetime.now():%H:%M:%S}] got reservation: {reservation}")
            for ticket in reservation.tickets:
                print(f"  - {ticket}")

            if car_filter is not None:
                cars = {str(int(str(ticket.car))) for ticket in reservation.tickets}
                if cars != {car_filter}:
                    print(
                        f"[{datetime.now():%H:%M:%S}] wrong car {sorted(cars)} "
                        f"(want {car_filter}); canceling"
                    )
                    try:
                        srt.cancel(reservation)
                        print(f"[{datetime.now():%H:%M:%S}] canceled")
                    except Exception as exc:
                        print(
                            f"[{datetime.now():%H:%M:%S}] cancel failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                    time.sleep(interval)
                    continue

            count = len(success) + 1
            print(
                f"[{datetime.now():%H:%M:%S}] RESERVED "
                f"{count}/{target}: {reservation}"
            )
            notify_telegram(
                telegram_token,
                telegram_chat_id,
                (
                    f"SRT reserved {count}/{target}"
                    f"{f' car={car_filter}' if car_filter else ''}\n"
                    f"{dep}->{arr} {dep_date} {exact_time}\n"
                    f"{reservation}\n"
                    f"{ticket_lines}\n"
                    f"egress_ip={egress_ip}"
                ).strip(),
            )
            success.append(reservation)
            time.sleep(interval)

        done_msg = (
            f"SRT done: {len(success)}/{target} reserved "
            f"({dep}->{arr} {exact_time}) egress_ip={egress_ip}"
        )
        print(f"[{datetime.now():%H:%M:%S}] {done_msg}")
        if success:
            notify_telegram(telegram_token, telegram_chat_id, done_msg)
        return 0
    except Exception as exc:
        err = (
            f"SRT smoke error: {type(exc).__name__}: {exc}\n"
            f"egress_ip={egress_ip} attempts={attempt}"
        )
        print(f"[{datetime.now():%H:%M:%S}] {err}", file=sys.stderr)
        notify_telegram(telegram_token, telegram_chat_id, err)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
