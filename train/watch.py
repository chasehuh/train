from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from .notify import telegram as notify


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def watch_srt(
    *,
    client: Any,
    dep: str,
    arr: str,
    date: str,
    dep_time: str,
    trains: list[str],
    seat_class: str,
    interval: float,
    monitor_only: bool,
    telegram: tuple[str | None, str | None],
    max_attempts: int | None = None,
) -> int:
    from SRT import SeatType
    from SRT.passenger import Adult

    token, chat = telegram
    print(
        f"[{_stamp()}] watch srt {dep}->{arr} {date} {dep_time} "
        f"trains={trains or 'any'} class={seat_class} interval={interval}"
    )
    notify(
        token,
        chat,
        f"SRT watch started\n{dep}->{arr} {date} {dep_time}\n"
        f"trains {','.join(trains) or 'any'} class={seat_class}",
    )
    attempt = 0
    while True:
        attempt += 1
        try:
            found = client.search_train(dep, arr, date, dep_time, available_only=False)
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} search error: {type(exc).__name__}: {exc}")
            if max_attempts and attempt >= max_attempts:
                return 1
            time.sleep(interval or 3)
            continue

        picked = None
        kind = None
        status = []
        for train in found:
            no = str(int(train.train_number))
            if trains and no not in trains:
                continue
            if train.dep_time < dep_time:
                continue
            sp = train.special_seat_available()
            gen = train.general_seat_available()
            status.append(f"{no}=특{'O' if sp else 'X'}/일{'O' if gen else 'X'}")
            if picked is not None:
                continue
            if seat_class == "special" and sp:
                picked, kind = train, SeatType.SPECIAL_ONLY
            elif seat_class == "general" and gen:
                picked, kind = train, SeatType.GENERAL_ONLY
            elif seat_class == "any" and (sp or gen):
                picked, kind = train, (
                    SeatType.SPECIAL_ONLY if sp else SeatType.GENERAL_ONLY
                )

        print(f"[{_stamp()}] #{attempt} {' '.join(status) or 'no trains'}")
        if picked is None or monitor_only:
            if max_attempts and attempt >= max_attempts:
                return 1 if picked is None else 0
            time.sleep(interval or 3)
            continue

        print(f"[{_stamp()}] #{attempt} try {picked}")
        try:
            reservation = client.reserve(
                picked, passengers=[Adult(1)], special_seat=kind
            )
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} reserve failed: {type(exc).__name__}: {exc}")
            if max_attempts and attempt >= max_attempts:
                return 1
            time.sleep(interval or 3)
            continue

        lines = "\n".join(f"  - {ticket}" for ticket in reservation.tickets)
        print(f"[{_stamp()}] RESERVED {reservation}")
        print(lines)
        notify(token, chat, f"SRT RESERVED\n{reservation}\n{lines}")
        return 0


def watch_korail(
    *,
    client: Any,
    dep: str,
    arr: str,
    date: str,
    dep_time: str,
    trains: list[str],
    end_time: str | None,
    seat_class: str,
    interval: float,
    monitor_only: bool,
    telegram: tuple[str | None, str | None],
    max_attempts: int | None = None,
) -> int:
    from korail2 import ReserveOption

    token, chat = telegram
    print(
        f"[{_stamp()}] watch ktx {dep}->{arr} {date} {dep_time} "
        f"trains={trains or 'any'} class={seat_class} interval={interval}"
    )
    notify(
        token,
        chat,
        f"Korail watch started\n{dep}->{arr} {date} {dep_time}\n"
        f"trains {','.join(trains) or 'any'} class={seat_class}",
    )
    attempt = 0
    while True:
        attempt += 1
        try:
            found = client.search_train(
                dep, arr, date, dep_time, include_no_seats=True
            )
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} search error: {type(exc).__name__}: {exc}")
            if max_attempts and attempt >= max_attempts:
                return 1
            time.sleep(interval or 3)
            continue

        picked = None
        status = []
        for train in found:
            no = str(train.train_no).lstrip("0")
            if trains and no not in trains:
                continue
            if end_time and train.dep_time > end_time:
                continue
            gen = train.has_general_seat()
            sp = train.has_special_seat()
            status.append(f"{no}=특{'O' if sp else 'X'}/일{'O' if gen else 'X'}")
            if picked is not None:
                continue
            if seat_class == "special" and sp:
                picked = train
            elif seat_class == "general" and gen:
                picked = train
            elif seat_class == "any" and (sp or gen):
                picked = train

        print(f"[{_stamp()}] #{attempt} {' '.join(status) or 'no trains'}")
        if picked is None or monitor_only:
            if max_attempts and attempt >= max_attempts:
                return 1 if picked is None else 0
            time.sleep(interval or 3)
            continue

        option = {
            "special": ReserveOption.SPECIAL_ONLY,
            "general": ReserveOption.GENERAL_ONLY,
            "any": (
                ReserveOption.SPECIAL_FIRST
                if picked.has_special_seat()
                else ReserveOption.GENERAL_ONLY
            ),
        }[seat_class]
        print(f"[{_stamp()}] #{attempt} try {picked}")
        try:
            reservation = client.reserve(picked, option=option)
        except Exception as exc:
            print(f"[{_stamp()}] #{attempt} reserve failed: {type(exc).__name__}: {exc}")
            if max_attempts and attempt >= max_attempts:
                return 1
            time.sleep(interval or 3)
            continue

        print(f"[{_stamp()}] RESERVED {reservation}")
        notify(token, chat, f"Korail RESERVED\n{reservation}")
        return 0
