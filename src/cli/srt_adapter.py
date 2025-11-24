from __future__ import annotations

from typing import Optional

from srt_backend import SRT
from srt_backend.errors import SRTResponseError
from srt_backend.train import SRTTrain

from .passengers import build_srt_passengers
from .types import PassengerCounts, map_srt_seat_priority, map_window_preference


def search(
    user: str,
    password: str,
    dep: str,
    arr: str,
    date: Optional[str],
    time: Optional[str],
    time_limit: Optional[str],
    available_only: bool,
):
    client = SRT(user, password, auto_login=True)
    trains = client.search_train(
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        available_only=available_only,
    )
    return trains


def reserve(
    user: str,
    password: str,
    train: SRTTrain,
    counts: PassengerCounts,
    seat_priority: str,
    window: Optional[str],
    standby: bool,
):
    client = SRT(user, password, auto_login=True)
    passengers = build_srt_passengers(counts)
    special = map_srt_seat_priority(seat_priority)
    window_pref = map_window_preference(window)
    if standby:
        return client.reserve_standby(train, passengers=passengers, special_seat=special)
    return client.reserve(
        train, passengers=passengers, special_seat=special, window_seat=window_pref
    )


def list_reservations(user: str, password: str, paid_only: bool = False):
    client = SRT(user, password, auto_login=True)
    return client.get_reservations(paid_only=paid_only)


def cancel(user: str, password: str, reservation_id: str):
    client = SRT(user, password, auto_login=True)
    return client.cancel(int(reservation_id))
