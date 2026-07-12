"""In-process concurrent job supervisor (ThreadPoolExecutor).

One Railway worker replica runs up to WORKER_CONCURRENCY poll loops in parallel,
like opening N terminals on one machine. Claiming stays SKIP LOCKED so threads
never take the same job.
"""

from __future__ import annotations

import os
import signal
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable
from uuid import UUID

ClaimFn = Callable[[], dict[str, Any] | None]
RunJobFn = Callable[[dict[str, Any]], None]
LogFn = Callable[[str], None]


def parse_concurrency(raw: str | None = None) -> int:
    """Parse WORKER_CONCURRENCY; default 3, min 1, soft-cap 8."""
    if raw is None:
        raw = os.environ.get("WORKER_CONCURRENCY", "3")
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        n = 3
    if n < 1:
        return 1
    if n > 8:
        return 8
    return n


def run_queue_supervisor(
    *,
    claim_job: ClaimFn,
    run_job: RunJobFn,
    concurrency: int,
    idle_sleep: float = 1.5,
    should_stop: Callable[[], bool] | None = None,
    log: LogFn | None = None,
) -> None:
    """Claim queued jobs and run them concurrently up to ``concurrency`` slots.

    Parameters are injectable so unit tests can prove overlapping execution
    without Postgres or real rail clients.
    """
    log = log or (lambda msg: print(f"[{datetime.now():%H:%M:%S}] {msg}"))
    concurrency = max(1, concurrency)
    stop = should_stop or (lambda: False)

    active: dict[UUID, Future[None]] = {}

    def _reap() -> None:
        done = [job_id for job_id, fut in active.items() if fut.done()]
        for job_id in done:
            fut = active.pop(job_id)
            try:
                fut.result()
            except Exception as exc:  # pragma: no cover - defensive; run_job should catch
                log(f"job={job_id} supervisor caught: {type(exc).__name__}: {exc}")
            log(f"slot freed job={job_id} active_slots={len(active)}/{concurrency}")

    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="train-job") as pool:
        log(f"supervisor start concurrency={concurrency}")
        while not stop():
            _reap()

            while len(active) < concurrency and not stop():
                try:
                    job = claim_job()
                except Exception as exc:
                    log(f"claim error: {type(exc).__name__}: {exc}")
                    break
                if not job:
                    break
                job_id = job["id"]
                fut = pool.submit(run_job, job)
                active[job_id] = fut
                log(f"submitted job={job_id} active_slots={len(active)}/{concurrency}")

            time.sleep(idle_sleep)

        # Stop claiming; wait briefly for in-flight jobs (SIGTERM path).
        log(f"supervisor stopping; waiting for {len(active)} active job(s)")
        deadline = time.monotonic() + 30.0
        while active and time.monotonic() < deadline:
            _reap()
            if active:
                time.sleep(0.2)
        if active:
            log(f"supervisor exit with {len(active)} job(s) still running")
        else:
            log("supervisor exit clean")


def install_sigterm_flag() -> Callable[[], bool]:
    """Return a should_stop callback that flips True on SIGTERM/SIGINT."""
    state = {"stop": False}

    def _handler(signum: int, _frame: Any) -> None:
        state["stop"] = True
        print(f"[{datetime.now():%H:%M:%S}] received signal {signum}; stopping claims")

    try:
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
    except (ValueError, OSError):  # pragma: no cover - non-main thread
        pass

    return lambda: state["stop"]
