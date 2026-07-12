"""Search SRT/Korail trains for the booking console (login + one-shot search)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from worker.rail_verify import normalize_rail_id

Carrier = Literal["srt", "korail"]
SeatClass = Literal["general", "special"]


@dataclass(frozen=True)
class SearchError:
    error: str
    message: str
    status: int = 400


def _hhmmss_to_display(raw: str | None) -> str:
    if not raw or len(raw) < 4:
        return "--:--"
    return f"{raw[0:2]}:{raw[2:4]}"


def _duration_minutes(dep_time: str | None, arr_time: str | None) -> int | None:
    if not dep_time or not arr_time or len(dep_time) < 6 or len(arr_time) < 6:
        return None
    try:
        dep = datetime.strptime(dep_time[:6], "%H%M%S")
        arr = datetime.strptime(arr_time[:6], "%H%M%S")
    except ValueError:
        return None
    if arr < dep:
        arr += timedelta(days=1)
    return int((arr - dep).total_seconds() // 60)


def _duration_label(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    hours, mins = divmod(minutes, 60)
    if hours <= 0:
        return f"{mins}분"
    if mins == 0:
        return f"{hours}시간"
    return f"{hours}시간 {mins}분"


def serialize_srt_train(train: Any) -> dict[str, Any]:
    dep_time = str(getattr(train, "dep_time", "") or "")
    arr_time = str(getattr(train, "arr_time", "") or "")
    general_ok = bool(train.general_seat_available())
    special_ok = bool(train.special_seat_available())
    minutes = _duration_minutes(dep_time, arr_time)
    return {
        "carrier": "srt",
        "train_type": str(getattr(train, "train_name", "SRT") or "SRT"),
        "train_number": str(getattr(train, "train_number", "") or ""),
        "dep": str(getattr(train, "dep_station_name", "") or ""),
        "arr": str(getattr(train, "arr_station_name", "") or ""),
        "dep_date": str(getattr(train, "dep_date", "") or ""),
        "dep_time": dep_time,
        "arr_time": arr_time,
        "dep_display": _hhmmss_to_display(dep_time),
        "arr_display": _hhmmss_to_display(arr_time),
        "duration_min": minutes,
        "duration_label": _duration_label(minutes),
        "general": {
            "available": general_ok,
            "label": "일반실",
            "state": str(getattr(train, "general_seat_state", "") or ""),
            "price": None,
        },
        "special": {
            "available": special_ok,
            "label": "특실",
            "state": str(getattr(train, "special_seat_state", "") or ""),
            "price": None,
        },
        "has_seat": bool(train.seat_available()),
    }


def serialize_korail_train(train: Any) -> dict[str, Any]:
    dep_time = str(getattr(train, "dep_time", "") or "")
    arr_time = str(getattr(train, "arr_time", "") or "")
    general_ok = bool(train.has_general_seat())
    special_ok = bool(train.has_special_seat())
    minutes = _duration_minutes(dep_time, arr_time)
    return {
        "carrier": "korail",
        "train_type": str(getattr(train, "train_type_name", "KTX") or "KTX"),
        "train_number": str(getattr(train, "train_no", "") or ""),
        "dep": str(getattr(train, "dep_name", "") or ""),
        "arr": str(getattr(train, "arr_name", "") or ""),
        "dep_date": str(getattr(train, "dep_date", "") or ""),
        "dep_time": dep_time,
        "arr_time": arr_time,
        "dep_display": _hhmmss_to_display(dep_time),
        "arr_display": _hhmmss_to_display(arr_time),
        "duration_min": minutes,
        "duration_label": _duration_label(minutes),
        "general": {
            "available": general_ok,
            "label": "일반실",
            "state": str(getattr(train, "general_seat", "") or ""),
            "price": None,
        },
        "special": {
            "available": special_ok,
            "label": "특실",
            "state": str(getattr(train, "special_seat", "") or ""),
            "price": None,
        },
        "has_seat": bool(train.has_seat()),
    }


def search_trains(
    carrier: Carrier,
    raw_id: str,
    password: str,
    dep: str,
    arr: str,
    date: str,
    time: str = "000000",
    *,
    available_only: bool = False,
) -> tuple[list[dict[str, Any]] | None, SearchError | None]:
    """Login and search. Returns (trains, None) or (None, error)."""
    user = normalize_rail_id(carrier, raw_id)
    pw = password or ""
    dep = (dep or "").strip()
    arr = (arr or "").strip()
    date = (date or "").strip()
    time = (time or "000000").strip() or "000000"

    if not user or not pw:
        return None, SearchError(
            error="validation_failed",
            message="id and password are required",
            status=400,
        )
    if not dep or not arr:
        return None, SearchError(
            error="validation_failed",
            message="dep and arr are required",
            status=400,
        )
    if len(date) != 8 or not date.isdigit():
        return None, SearchError(
            error="validation_failed",
            message="date must be YYYYMMDD",
            status=400,
        )
    if len(time) != 6 or not time.isdigit():
        return None, SearchError(
            error="validation_failed",
            message="time must be HHMMSS",
            status=400,
        )

    try:
        if carrier == "srt":
            from srt_backend import SRT

            srt = SRT(user, pw, verbose=False)
            trains = srt.search_train(
                dep,
                arr,
                date,
                time,
                available_only=available_only,
            )
            return [serialize_srt_train(t) for t in trains], None

        from korail_backend.korail2 import Korail

        korail = Korail(user, pw, auto_login=True)
        if not korail.logined:
            return None, SearchError(
                error="login_failed",
                message="Korail login failed",
                status=401,
            )
        trains = korail.search_train(
            dep,
            arr,
            date,
            time,
            include_no_seats=not available_only,
        )
        return [serialize_korail_train(t) for t in trains], None
    except ValueError as exc:
        return None, SearchError(
            error="validation_failed",
            message=str(exc) or "invalid search parameters",
            status=400,
        )
    except Exception as exc:
        return None, SearchError(
            error="search_failed",
            message=f"{carrier} search failed: {type(exc).__name__}",
            status=502,
        )
