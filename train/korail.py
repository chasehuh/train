"""Korail client factory and the watch/reserve loop."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

from .notify import telegram as notify
from .spec import JobSpec

EXIT_RESERVED = 0
EXIT_FAILED = 1
EXIT_DEADLINE = 3


def normalize_id(raw_id: str) -> str:
    """Normalize phone-like IDs to ###-####-#### for Korail."""
    digits = "".join(ch for ch in raw_id if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return raw_id


def make_client():
    from korail2 import Korail

    user = os.environ.get("KORAIL_ID")
    pw = os.environ.get("KORAIL_PW")
    if not user or not pw:
        raise SystemExit("KORAIL_ID / KORAIL_PW required")
    client = Korail(normalize_id(user), pw, auto_login=True)
    if not client.logined:
        raise SystemExit(
            f"Korail login failed: {client.last_login_error_code} {client.last_login_error_message}"
        )
    return client


def telegram_target() -> tuple[str | None, str | None]:
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def watch(
    *,
    client: Any,
    spec: JobSpec,
    telegram: tuple[str | None, str | None],
    max_attempts: int | None = None,
    deadline: float | None = None,
) -> int:
    """Poll until a seat is held. Returns EXIT_RESERVED / EXIT_FAILED / EXIT_DEADLINE."""
    from korail2 import ReserveOption, SeatLetterMismatchError

    token, chat = telegram
    trains = spec.trains
    interval = spec.interval_sec
    print(
        f"[{_stamp()}] watch korail {spec.dep}->{spec.arr} {spec.date} {spec.time} "
        f"trains={trains or 'any'} class={spec.seat_class} "
        f"letter={spec.seat_letter or '-'} interval={interval}"
    )
    notify(
        token,
        chat,
        f"Korail watch started\n{spec.dep}->{spec.arr} {spec.date} {spec.time}\n"
        f"trains {','.join(trains) or 'any'} class={spec.seat_class}"
        + (f" letter={spec.seat_letter}" if spec.seat_letter else ""),
    )
    attempt = 0

    def _sleep_or_stop(code: int) -> int | None:
        if max_attempts and attempt >= max_attempts:
            return code
        if deadline is not None and time.time() >= deadline:
            print(f"[{_stamp()}] deadline reached after {attempt} attempts")
            return EXIT_DEADLINE
        time.sleep(interval or 3)
        return None

    while True:
        attempt += 1
        try:
            found = client.search_train(
                spec.dep, spec.arr, spec.date, spec.time, include_no_seats=True
            )
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} search error: {type(exc).__name__}: {exc}")
            stop = _sleep_or_stop(EXIT_FAILED)
            if stop is not None:
                return stop
            continue

        picked = None
        status = []
        for train in found:
            no = str(train.train_no).lstrip("0")
            if trains and no not in trains:
                continue
            if spec.end_time and train.dep_time > spec.end_time:
                continue
            gen = train.has_general_seat()
            sp = train.has_special_seat()
            status.append(f"{no}=특{'O' if sp else 'X'}/일{'O' if gen else 'X'}")
            if picked is not None:
                continue
            if spec.seat_class == "special" and sp:
                picked = train
            elif spec.seat_class == "general" and gen:
                picked = train
            elif spec.seat_class == "any" and (sp or gen):
                picked = train

        print(f"[{_stamp()}] #{attempt} {' '.join(status) or 'no trains'}")
        if picked is None or spec.monitor_only:
            stop = _sleep_or_stop(EXIT_FAILED if picked is None else EXIT_RESERVED)
            if stop is not None:
                return stop
            continue

        option = {
            "special": ReserveOption.SPECIAL_ONLY,
            "general": ReserveOption.GENERAL_ONLY,
            "any": (
                ReserveOption.SPECIAL_FIRST
                if picked.has_special_seat()
                else ReserveOption.GENERAL_ONLY
            ),
        }[spec.seat_class]
        print(f"[{_stamp()}] #{attempt} try {picked}")
        try:
            reservation = client.reserve(
                picked, option=option, seat_letter=spec.seat_letter
            )
        except SeatLetterMismatchError as exc:
            print(
                f"[{_stamp()}] #{attempt} wrong letter {exc.seat_no}, "
                f"wanted {exc.wanted}; cancelled"
            )
            stop = _sleep_or_stop(EXIT_FAILED)
            if stop is not None:
                return stop
            continue
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} reserve failed: {type(exc).__name__}: {exc}")
            stop = _sleep_or_stop(EXIT_FAILED)
            if stop is not None:
                return stop
            continue

        print(f"[{_stamp()}] RESERVED {reservation}")
        notify(token, chat, f"Korail RESERVED\n{reservation}")
        return EXIT_RESERVED
