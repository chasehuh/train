"""SRT poll/reserve runner for a single queue job."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from srt_backend import SRT, SeatType
from srt_backend.passenger import Adult

from worker.exceptions import JobCanceled

NotifyFn = Callable[[str], None]
StopFn = Callable[[], bool]


def resolve_srt_credentials(job: dict[str, Any]) -> tuple[str, str]:
    from .crypto_util import decrypt_credentials
    from .rail_verify import allow_env_creds, normalize_rail_id

    if job.get("credentials_enc"):
        data = decrypt_credentials(job["credentials_enc"])
        user = normalize_rail_id("srt", str(data["id"]))
        return user, str(data["pw"])

    if not allow_env_creds():
        raise RuntimeError(
            "SRT credentials missing: job requires credentials_enc "
            "(set ALLOW_ENV_CREDS=true only for smoke/dev env fallback)"
        )

    user = os.environ.get("SRT_ID")
    pw = os.environ.get("SRT_PW")
    if not user or not pw:
        raise RuntimeError("SRT credentials missing (job credentials_enc or SRT_ID/SRT_PW)")
    return normalize_rail_id("srt", user), pw


def run_srt_job(
    job: dict[str, Any],
    notify: NotifyFn | None = None,
    should_stop: StopFn | None = None,
) -> dict[str, Any]:
    notify = notify or (lambda _msg: None)
    should_stop = should_stop or (lambda: False)

    user, pw = resolve_srt_credentials(job)
    dep = job["dep"]
    arr = job["arr"]
    dep_date = job["travel_date"]
    exact_time = job["dep_time"]
    target = int(job["target_seats"])
    car_filter = str(job["car"]) if job.get("car") is not None else None
    interval = float(job["interval_sec"])
    dry_run = bool(job["dry_run"])
    max_attempts = job.get("max_attempts")

    srt = SRT(user, pw, verbose=False)
    notify(f"SRT login ok for job {job['id']}")

    success: list[str] = []
    attempt = 0
    while len(success) < target:
        if should_stop():
            raise JobCanceled(f"job {job['id']} canceled")
        attempt += 1
        if dry_run and max_attempts is not None and attempt > int(max_attempts):
            return {
                "mode": "dry_run",
                "attempts": attempt - 1,
                "message": f"dry-run finished after {max_attempts} attempts",
                "reservations": success,
            }

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
            notify(f"#{attempt} search error: {type(exc).__name__}: {exc}")
            time.sleep(interval)
            continue

        if not train:
            if attempt == 1 or attempt % 20 == 0:
                notify(f"#{attempt} no available seat")
            time.sleep(interval)
            continue

        notify(f"#{attempt} candidate {train}")
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
            notify(f"#{attempt} reserve failed: {type(exc).__name__}: {exc}")
            time.sleep(interval)
            continue

        tickets = [str(t) for t in reservation.tickets]
        if car_filter is not None:
            cars = {str(int(str(t.car))) for t in reservation.tickets}
            if cars != {car_filter}:
                notify(f"wrong car {sorted(cars)} (want {car_filter}); canceling")
                try:
                    srt.cancel(reservation)
                except Exception as exc:
                    notify(f"cancel failed: {type(exc).__name__}: {exc}")
                time.sleep(interval)
                continue

        success.append(str(reservation))
        notify(f"RESERVED {len(success)}/{target}: {reservation}\n" + "\n".join(f"  - {t}" for t in tickets))
        time.sleep(interval)

    return {
        "mode": "reserve",
        "attempts": attempt,
        "reservations": success,
        "message": f"done {len(success)}/{target}",
    }
