from __future__ import annotations

from typing import Optional, Literal

from korail_backend.korail2 import TrainType
from srt_backend.train import SRTTrain
from korail_backend.korail2 import Train as KorailTrain

from . import srt_adapter, korail_adapter
from .types import PassengerCounts, map_korail_train_type

BackendType = Literal["srt", "korail", "auto"]


def choose_backend(backend: BackendType, train_type: str) -> BackendType:
    if backend != "auto":
        return backend
    if train_type.lower() == "srt":
        return "srt"
    return "korail"


def search(
    backend: BackendType,
    train_type: str,
    user: str,
    password: str,
    dep: str,
    arr: str,
    date: Optional[str],
    time: Optional[str],
    time_limit: Optional[str],
    available_only: bool,
    include_waiting: bool,
    counts: PassengerCounts,
):
    chosen = choose_backend(backend, train_type)
    if chosen == "srt":
        return srt_adapter.search(user, password, dep, arr, date, time, time_limit, available_only)
    # korail path
    kor_train_type = map_korail_train_type(train_type)
    return korail_adapter.search(
        user,
        password,
        dep,
        arr,
        date,
        time,
        kor_train_type,
        counts,
        include_no_seats=not available_only,
        include_waiting=include_waiting,
    )


def reserve(
    backend: BackendType,
    train_type: str,
    user: str,
    password: str,
    dep: str,
    arr: str,
    date: Optional[str],
    time: Optional[str],
    time_limit: Optional[str],
    seat_priority: str,
    window: Optional[str],
    standby: bool,
    try_waiting: bool,
    counts: PassengerCounts,
):
    chosen = choose_backend(backend, train_type)
    trains = search(
        backend=backend,
        train_type=train_type,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        available_only=True,
        include_waiting=try_waiting,
        counts=counts,
    )
    if not trains:
        return None
    train = trains[0]
    if chosen == "srt":
        assert isinstance(train, SRTTrain)
        return srt_adapter.reserve(
            user, password, train, counts=counts, seat_priority=seat_priority, window=window, standby=standby
        )
    else:
        assert isinstance(train, KorailTrain)
        return korail_adapter.reserve(
            user, password, train, counts=counts, seat_priority=seat_priority, try_waiting=try_waiting
        )


def list_reservations(backend: BackendType, train_type: str, user: str, password: str, paid_only: bool = False):
    chosen = choose_backend(backend, train_type)
    if chosen == "srt":
        return srt_adapter.list_reservations(user, password, paid_only=paid_only)
    return korail_adapter.list_reservations(user, password)


def cancel(backend: BackendType, train_type: str, user: str, password: str, reservation_id: str):
    chosen = choose_backend(backend, train_type)
    if chosen == "srt":
        return srt_adapter.cancel(user, password, reservation_id)
    return korail_adapter.cancel(user, password, reservation_id)
