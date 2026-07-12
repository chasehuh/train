"""Prove WORKER_CONCURRENCY runs jobs overlapping in one process."""

from __future__ import annotations

import threading
import time
import unittest
from uuid import uuid4

from worker.supervisor import parse_concurrency, run_queue_supervisor


class TestParseConcurrency(unittest.TestCase):
    def test_default_and_bounds(self) -> None:
        self.assertEqual(parse_concurrency(None), 3)
        self.assertEqual(parse_concurrency("3"), 3)
        self.assertEqual(parse_concurrency("0"), 1)
        self.assertEqual(parse_concurrency("-2"), 1)
        self.assertEqual(parse_concurrency("99"), 8)
        self.assertEqual(parse_concurrency("nope"), 3)


class TestOverlappingExecution(unittest.TestCase):
    def test_three_jobs_overlap_with_concurrency_3(self) -> None:
        jobs = [{"id": uuid4(), "carrier": "srt"} for _ in range(3)]
        pending = list(jobs)
        lock = threading.Lock()
        active = 0
        max_active = 0
        finished = 0
        start_times: list[float] = []
        end_times: list[float] = []

        def claim_job():
            return pending.pop(0) if pending else None

        def run_job(job: dict) -> None:
            nonlocal active, max_active, finished
            with lock:
                active += 1
                max_active = max(max_active, active)
                start_times.append(time.monotonic())
            time.sleep(0.35)
            with lock:
                active -= 1
                finished += 1
                end_times.append(time.monotonic())

        def should_stop() -> bool:
            with lock:
                return finished >= 3

        t0 = time.monotonic()
        run_queue_supervisor(
            claim_job=claim_job,
            run_job=run_job,
            concurrency=3,
            idle_sleep=0.05,
            should_stop=should_stop,
            log=lambda _msg: None,
        )
        elapsed = time.monotonic() - t0

        self.assertEqual(finished, 3)
        self.assertEqual(max_active, 3)
        # Serial would take ~1.05s; concurrent ~0.35s + overhead.
        self.assertLess(elapsed, 0.9)
        self.assertEqual(len(start_times), 3)
        # All three started before the first one finished.
        self.assertLess(max(start_times), min(end_times))

    def test_concurrency_1_is_serial(self) -> None:
        jobs = [{"id": uuid4(), "carrier": "srt"} for _ in range(3)]
        pending = list(jobs)
        lock = threading.Lock()
        active = 0
        max_active = 0
        finished = 0

        def claim_job():
            return pending.pop(0) if pending else None

        def run_job(job: dict) -> None:
            nonlocal active, max_active, finished
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.12)
            with lock:
                active -= 1
                finished += 1

        def should_stop() -> bool:
            with lock:
                return finished >= 3

        run_queue_supervisor(
            claim_job=claim_job,
            run_job=run_job,
            concurrency=1,
            idle_sleep=0.02,
            should_stop=should_stop,
            log=lambda _msg: None,
        )

        self.assertEqual(finished, 3)
        self.assertEqual(max_active, 1)


if __name__ == "__main__":
    unittest.main()
