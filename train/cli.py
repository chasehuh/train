#!/usr/bin/env python3
"""Korail (KTX / ITX) CLI: search, watch, reserve, reservations, doctor."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime

from .env import load_env
from .korail import EXIT_DEADLINE, make_client, telegram_target, watch
from .notify import telegram
from .spec import MAX_MINUTES, JobSpec, normalize_train_nos


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="train",
        description="Search, watch, and reserve Korail seats.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def trip(p: argparse.ArgumentParser) -> None:
        p.add_argument("--dep", required=True, help="Departure station, Korean")
        p.add_argument("--arr", required=True, help="Arrival station, Korean")
        p.add_argument("--date", default=_today(), help="YYYYMMDD")
        p.add_argument("--time", dest="dep_time", default="000000", help="HHMMSS search start")
        p.add_argument("--end-time", dest="end_time", help="HHMMSS latest departure")
        p.add_argument("--trains", help="Comma-separated train numbers, tried in order")

    def seat(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--class",
            dest="seat_class",
            choices=("any", "general", "special"),
            default="any",
            help="any = first of special or general",
        )
        p.add_argument("--seat-letter", help="Wanted seat letter (A/B/C/D); map first, else reserve+cancel")

    search = sub.add_parser("search", help="One-shot timetable lookup")
    trip(search)
    search.add_argument("--limit", type=int, default=20)

    w = sub.add_parser("watch", help="Poll until a seat opens, then reserve")
    trip(w)
    seat(w)
    w.add_argument("--interval", type=float, default=3.0)
    w.add_argument("--monitor-only", action="store_true")
    w.add_argument("--no-telegram", action="store_true")
    w.add_argument(
        "--max-minutes",
        type=int,
        help=f"Stop polling after N minutes (1..{MAX_MINUTES}); exit code {EXIT_DEADLINE}",
    )

    reserve = sub.add_parser("reserve", help="One-shot reserve (no poll loop)")
    trip(reserve)
    seat(reserve)

    sub.add_parser("reservations", help="List holds and tickets")
    sub.add_parser("doctor", help="Login and print status")
    return parser


def _spec(args: argparse.Namespace, **extra) -> JobSpec:
    data = {
        "dep": args.dep,
        "arr": args.arr,
        "date": args.date,
        "time": args.dep_time,
        "end_time": args.end_time,
        "trains": args.trains,
        "seat_class": getattr(args, "seat_class", "any"),
        "seat_letter": getattr(args, "seat_letter", None),
    }
    data.update(extra)
    try:
        return JobSpec.from_dict(data)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")


def cmd_search(args: argparse.Namespace) -> int:
    nos = normalize_train_nos(args.trains)
    korail = make_client()
    trains = korail.search_train(
        args.dep, args.arr, args.date, args.dep_time, include_no_seats=True
    )
    shown = 0
    for train in trains:
        no = str(train.train_no).lstrip("0")
        if nos and no not in nos:
            continue
        if args.end_time and train.dep_time > args.end_time:
            continue
        gen = train.has_general_seat()
        sp = train.has_special_seat()
        print(
            f"{no} {train.dep_time[:2]}:{train.dep_time[2:4]}->"
            f"{train.arr_time[:2]}:{train.arr_time[2:4]} "
            f"특={'O' if sp else 'X'} 일={'O' if gen else 'X'} | {train}"
        )
        shown += 1
        if shown >= args.limit:
            break
    if shown == 0:
        print("no matching Korail trains")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    spec = _spec(
        args,
        interval_sec=args.interval,
        monitor_only=args.monitor_only,
        max_minutes=args.max_minutes,
    )
    deadline = time.time() + args.max_minutes * 60 if args.max_minutes else None
    return watch(
        client=make_client(),
        spec=spec,
        telegram=(None, None) if args.no_telegram else telegram_target(),
        deadline=deadline,
    )


def cmd_reserve(args: argparse.Namespace) -> int:
    spec = _spec(args, interval_sec=0)
    return watch(
        client=make_client(),
        spec=spec,
        telegram=telegram_target(),
        max_attempts=1,
    )


def cmd_reservations(_: argparse.Namespace) -> int:
    korail = make_client()
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
    print("=== Korail ===")
    try:
        make_client()
        print("login ok")
    except Exception as exc:
        print("fail:", exc)
    token, chat = telegram_target()
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
