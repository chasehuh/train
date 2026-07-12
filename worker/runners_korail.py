"""Korail (KTX etc.) poll/reserve runner for a single queue job."""

from __future__ import annotations

import os
import time
from typing import Any, Callable

from korail_backend.korail2 import Korail, ReserveOption

from worker.exceptions import JobCanceled

NotifyFn = Callable[[str], None]
StopFn = Callable[[], bool]


def resolve_korail_credentials(job: dict[str, Any]) -> tuple[str, str]:
    from .crypto_util import decrypt_credentials

    if job.get("credentials_enc"):
        data = decrypt_credentials(job["credentials_enc"])
        return str(data["id"]), str(data["pw"])
    user = os.environ.get("KORAIL_ID")
    pw = os.environ.get("KORAIL_PW")
    if not user or not pw:
        raise RuntimeError(
            "Korail credentials missing (job credentials_enc or KORAIL_ID/KORAIL_PW)"
        )
    return user, pw


def run_korail_job(
    job: dict[str, Any],
    notify: NotifyFn | None = None,
    should_stop: StopFn | None = None,
) -> dict[str, Any]:
    notify = notify or (lambda _msg: None)
    should_stop = should_stop or (lambda: False)

    user, pw = resolve_korail_credentials(job)
    dep = job["dep"]
    arr = job["arr"]
    dep_date = job["travel_date"]
    exact_time = job["dep_time"]
    target = int(job["target_seats"])
    interval = float(job["interval_sec"])
    dry_run = bool(job["dry_run"])
    max_attempts = job.get("max_attempts")

    # Phone-like IDs: normalize if 11 digits
    digits = "".join(ch for ch in user if ch.isdigit())
    if len(digits) == 11:
        user = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"

    korail = Korail(user, pw, auto_login=True)
    if not korail.logined:
        raise RuntimeError("Korail login failed")
    notify(f"Korail login ok for job {job['id']}")

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
            trains = korail.search_train(
                dep,
                arr,
                dep_date,
                exact_time,
                include_no_seats=False,
            )
            # Exact departure match when possible
            train = next(
                (t for t in trains if getattr(t, "dep_time", None) == exact_time),
                trains[0] if trains else None,
            )
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
            reservation = korail.reserve(train, option=ReserveOption.GENERAL_ONLY)
        except Exception as exc:
            notify(f"#{attempt} reserve failed: {type(exc).__name__}: {exc}")
            time.sleep(interval)
            continue

        success.append(str(reservation))
        notify(f"RESERVED {len(success)}/{target}: {reservation}")
        time.sleep(interval)

    return {
        "mode": "reserve",
        "attempts": attempt,
        "reservations": success,
        "message": f"done {len(success)}/{target}",
    }
