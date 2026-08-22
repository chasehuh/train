#!/usr/bin/env python3
"""Unified Korail (KTX/ITX) + SRT CLI."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from .env import load_env
from .notify import telegram
from .watch import watch_korail, watch_srt


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _now_time() -> str:
    return datetime.now().strftime("%H%M%S")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="train",
        description="Search, watch, and reserve Korail + SRT seats.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def trip(p: argparse.ArgumentParser) -> None:
        p.add_argument("--carrier", choices=("srt", "ktx", "all"), default="srt")
        p.add_argument("--dep", required=True, help="Departure station, Korean")
        p.add_argument("--arr", required=True, help="Arrival station, Korean")
        p.add_argument("--date", default=_today(), help="YYYYMMDD")
        p.add_argument("--time", dest="dep_time", default="000000", help="HHMMSS search start")
        p.add_argument("--end-time", dest="end_time", help="HHMMSS latest departure")
        p.add_argument("--trains", help="Comma-separated train numbers, tried in order")

    search = sub.add_parser("search", help="One-shot timetable lookup")
    trip(search)
    search.add_argument("--limit", type=int, default=20)

    watch = sub.add_parser("watch", help="Poll until a seat opens, then reserve")
    trip(watch)
    watch.add_argument("--interval", type=float, default=3.0)
    watch.add_argument("--monitor-only", action="store_true")
    watch.add_argument(
        "--class",
        dest="seat_class",
        choices=("any", "general", "special"),
        default="any",
        help="any = first of special or general",
    )
    watch.add_argument("--no-telegram", action="store_true")

    reserve = sub.add_parser("reserve", help="One-shot reserve (no poll loop)")
    trip(reserve)
    reserve.add_argument(
        "--class",
        dest="seat_class",
        choices=("any", "general", "special"),
        default="any",
    )

    res = sub.add_parser("reservations", help="List holds and tickets")
    res.add_argument("--carrier", choices=("srt", "ktx", "all"), default="all")

    sub.add_parser("doctor", help="Login both carriers and print status")
    return parser


def _train_nos(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [n.strip().lstrip("0") or "0" for n in raw.split(",") if n.strip()]


def _korail():
    from korail2 import Korail
    from korail2.monitor import normalize_id

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


def _srt():
    from SRT import SRT

    user = os.environ.get("SRT_ID")
    pw = os.environ.get("SRT_PW")
    if not user or not pw:
        raise SystemExit("SRT_ID / SRT_PW required")
    return SRT(user, pw, verbose=False)


def _print_srt_trains(trains, nos: list[str], end_time: str | None, limit: int) -> None:
    shown = 0
    for train in trains:
        no = str(int(train.train_number))
        if nos and no not in nos:
            continue
        if end_time and train.dep_time > end_time:
            continue
        print(
            f"{no} {train.dep_time[:2]}:{train.dep_time[2:4]}->"
            f"{train.arr_time[:2]}:{train.arr_time[2:4]} "
            f"특={'O' if train.special_seat_available() else 'X'} "
            f"일={'O' if train.general_seat_available() else 'X'} | {train}"
        )
        shown += 1
        if shown >= limit:
            break
    if shown == 0:
        print("no matching SRT trains")


def _print_ktx_trains(trains, nos: list[str], end_time: str | None, limit: int) -> None:
    shown = 0
    for train in trains:
        no = str(train.train_no).lstrip("0")
        if nos and no not in nos:
            continue
        if end_time and train.dep_time > end_time:
            continue
        gen = train.has_general_seat()
        sp = train.has_special_seat()
        print(
            f"{no} {train.dep_time[:2]}:{train.dep_time[2:4]}->"
            f"{train.arr_time[:2]}:{train.arr_time[2:4]} "
            f"특={'O' if sp else 'X'} 일={'O' if gen else 'X'} | {train}"
        )
        shown += 1
        if shown >= limit:
            break
    if shown == 0:
        print("no matching Korail trains")


def cmd_search(args: argparse.Namespace) -> int:
    nos = _train_nos(args.trains)
    if args.carrier in ("srt", "all"):
        print("=== SRT ===")
        srt = _srt()
        trains = srt.search_train(
            args.dep, args.arr, args.date, args.dep_time, available_only=False
        )
        _print_srt_trains(trains, nos, args.end_time, args.limit)
    if args.carrier in ("ktx", "all"):
        print("=== Korail ===")
        korail = _korail()
        trains = korail.search_train(
            args.dep, args.arr, args.date, args.dep_time, include_no_seats=True
        )
        _print_ktx_trains(trains, nos, args.end_time, args.limit)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    if args.carrier == "all":
        raise SystemExit("watch needs --carrier srt or --carrier ktx")
    tg = (None, None)
    if not args.no_telegram:
        tg = (
            os.environ.get("TELEGRAM_BOT_TOKEN"),
            os.environ.get("TELEGRAM_CHAT_ID"),
        )
    nos = _train_nos(args.trains)
    if args.carrier == "srt":
        return watch_srt(
            client=_srt(),
            dep=args.dep,
            arr=args.arr,
            date=args.date,
            dep_time=args.dep_time,
            trains=nos,
            seat_class=args.seat_class,
            interval=args.interval,
            monitor_only=args.monitor_only,
            telegram=tg,
        )
    return watch_korail(
        client=_korail(),
        dep=args.dep,
        arr=args.arr,
        date=args.date,
        dep_time=args.dep_time,
        trains=nos,
        end_time=args.end_time,
        seat_class=args.seat_class,
        interval=args.interval,
        monitor_only=args.monitor_only,
        telegram=tg,
    )


def cmd_reserve(args: argparse.Namespace) -> int:
    args.monitor_only = False
    args.interval = 0
    args.no_telegram = False
    # one attempt: watch loop with interval 0 still loops; use watch once via monitor_only false
    # Dedicated one-shot in watch with max_attempts=1
    if args.carrier == "all":
        raise SystemExit("reserve needs --carrier srt or --carrier ktx")
    tg = (
        os.environ.get("TELEGRAM_BOT_TOKEN"),
        os.environ.get("TELEGRAM_CHAT_ID"),
    )
    nos = _train_nos(args.trains)
    if args.carrier == "srt":
        return watch_srt(
            client=_srt(),
            dep=args.dep,
            arr=args.arr,
            date=args.date,
            dep_time=args.dep_time,
            trains=nos,
            seat_class=args.seat_class,
            interval=0,
            monitor_only=False,
            telegram=tg,
            max_attempts=1,
        )
    return watch_korail(
        client=_korail(),
        dep=args.dep,
        arr=args.arr,
        date=args.date,
        dep_time=args.dep_time,
        trains=nos,
        end_time=args.end_time,
        seat_class=args.seat_class,
        interval=0,
        monitor_only=False,
        telegram=tg,
        max_attempts=1,
    )


def cmd_reservations(args: argparse.Namespace) -> int:
    if args.carrier in ("srt", "all"):
        print("=== SRT ===")
        srt = _srt()
        holds = srt.get_reservations()
        if not holds:
            print("(none)")
        for item in holds:
            print(item, "paid=" + str(item.paid))
            for ticket in item.tickets:
                print(" ", ticket)
    if args.carrier in ("ktx", "all"):
        print("=== Korail ===")
        korail = _korail()
        holds = korail.reservations()
        if not holds:
            print("(none)")
        for item in holds:
            print(item)
        try:
            tickets = korail.tickets()
        except Exception as exc:
            print("paid tickets:", type(exc).__name__, exc)
            tickets = []
        if tickets:
            print("paid:")
            for ticket in tickets:
                print(" ", ticket)
        elif holds is not None:
            print("paid: (none)")
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    print("=== SRT ===")
    try:
        _srt()
        print("login ok")
    except Exception as exc:
        print("fail:", exc)
    print("=== Korail ===")
    try:
        _korail()
        print("login ok")
    except Exception as exc:
        print("fail:", exc)
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    print("=== Telegram ===")
    print("configured" if token and chat else "missing TELEGRAM_*")
    if token and chat:
        telegram(token, chat, "train doctor: telegram ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    commands = {
        "search": cmd_search,
        "watch": cmd_watch,
        "reserve": cmd_reserve,
        "reservations": cmd_reservations,
        "doctor": cmd_doctor,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
