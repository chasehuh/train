from __future__ import annotations

import time
from typing import Optional

import typer
from rich.console import Console

from .backends import BackendType, cancel as backend_cancel, list_reservations, reserve as backend_reserve, search as backend_search
from .types import PassengerCounts
from .schemas import BaseSearchModel, PassengerCountsModel

app = typer.Typer(help="Unified CLI for Korail/SRT (train-type driven routing)")
console = Console()


def passenger_options():
    return {
        "adult": typer.Option(1, help="성인 인원"),
        "child": typer.Option(0, help="어린이 인원"),
        "senior": typer.Option(0, help="경로 인원"),
        "disability1": typer.Option(0, help="장애 1~3급 인원"),
        "disability2": typer.Option(0, help="장애 4~6급 인원"),
        "toddler": typer.Option(0, help="유아(코레일 전용) 인원"),
    }


@app.command()
def search(
    backend: BackendType = typer.Option("auto", help="auto|srt|korail"),
    user: str = typer.Option(..., "--id", help="ID (membership/email/phone)"),
    password: str = typer.Option(..., "--pw", help="Password"),
    dep: str = typer.Option(..., help="Departure station"),
    arr: str = typer.Option(..., help="Arrival station"),
    date: Optional[str] = typer.Option(None, help="YYYYMMDD"),
    time: Optional[str] = typer.Option(None, help="HHMMSS"),
    time_limit: Optional[str] = typer.Option(None, help="HHMMSS upper bound"),
    train_type: str = typer.Option("srt", help="srt, ktx, all, etc."),
    available_only: bool = typer.Option(True, help="Only show available seats"),
    include_waiting: bool = typer.Option(False, help="Include waitlist (Korail)"),
    seat_priority: str = typer.Option("general-first", help="Seat priority"),
    window_seat: Optional[str] = typer.Option(None, help="window|aisle|any (SRT)"),
    **counts_kwargs,
):
    # validate options with pydantic (zod-like)
    BaseSearchModel(
        backend=backend,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        train_type=train_type,
        available_only=available_only,
        include_waiting=include_waiting,
        seat_priority=seat_priority,
        window_seat=window_seat,
    )
    PassengerCountsModel(**counts_kwargs)
    counts = PassengerCounts(**counts_kwargs)
    trains = backend_search(
        backend=backend,
        train_type=train_type,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        available_only=available_only,
        include_waiting=include_waiting,
        counts=counts,
    )
    if not trains:
        console.print("[yellow]No trains found[/yellow]")
        raise typer.Exit(code=1)

    for t in trains:
        console.print(str(t))


@app.command()
def reserve(
    backend: BackendType = typer.Option("auto", help="auto|srt|korail"),
    user: str = typer.Option(..., "--id", help="ID (membership/email/phone)"),
    password: str = typer.Option(..., "--pw", help="Password"),
    dep: str = typer.Option(..., help="Departure station"),
    arr: str = typer.Option(..., help="Arrival station"),
    date: Optional[str] = typer.Option(None, help="YYYYMMDD"),
    time: Optional[str] = typer.Option(None, help="HHMMSS"),
    time_limit: Optional[str] = typer.Option(None, help="HHMMSS upper bound"),
    train_type: str = typer.Option("srt", help="srt, ktx, all, etc."),
    seat_priority: str = typer.Option("general-first", help="Seat priority"),
    window_seat: Optional[str] = typer.Option(None, help="window|aisle|any (SRT)"),
    standby: bool = typer.Option(False, help="SRT standby(예약대기)"),
    try_waiting: bool = typer.Option(False, help="Korail waitlist if sold out"),
    **counts_kwargs,
):
    BaseSearchModel(
        backend=backend,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        train_type=train_type,
        available_only=True,
        include_waiting=try_waiting,
        seat_priority=seat_priority,
        window_seat=window_seat,
    )
    PassengerCountsModel(**counts_kwargs)
    counts = PassengerCounts(**counts_kwargs)
    reservation = backend_reserve(
        backend=backend,
        train_type=train_type,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        seat_priority=seat_priority,
        window=window_seat,
        standby=standby,
        try_waiting=try_waiting,
        counts=counts,
    )
    if reservation is None:
        console.print("[yellow]No available trains[/yellow]")
        raise typer.Exit(code=1)
    console.print(str(reservation))


@app.command()
def poll_reserve(
    backend: BackendType = typer.Option("auto", help="auto|srt|korail"),
    user: str = typer.Option(..., "--id", help="ID (membership/email/phone)"),
    password: str = typer.Option(..., "--pw", help="Password"),
    dep: str = typer.Option(..., help="Departure station"),
    arr: str = typer.Option(..., help="Arrival station"),
    date: Optional[str] = typer.Option(None, help="YYYYMMDD"),
    time: Optional[str] = typer.Option(None, help="HHMMSS"),
    time_limit: Optional[str] = typer.Option(None, help="HHMMSS upper bound"),
    train_type: str = typer.Option("srt", help="srt, ktx, all, etc."),
    seat_priority: str = typer.Option("general-first", help="Seat priority"),
    window_seat: Optional[str] = typer.Option(None, help="window|aisle|any (SRT)"),
    standby: bool = typer.Option(False, help="SRT standby(예약대기)"),
    try_waiting: bool = typer.Option(False, help="Korail waitlist if sold out"),
    poll_interval: float = typer.Option(5.0, help="Seconds between polls"),
    max_attempts: int = typer.Option(0, help="0 for infinite"),
    **counts_kwargs,
):
    BaseSearchModel(
        backend=backend,
        user=user,
        password=password,
        dep=dep,
        arr=arr,
        date=date,
        time=time,
        time_limit=time_limit,
        train_type=train_type,
        available_only=True,
        include_waiting=try_waiting,
        seat_priority=seat_priority,
        window_seat=window_seat,
    )
    PassengerCountsModel(**counts_kwargs)
    counts = PassengerCounts(**counts_kwargs)
    attempt = 0
    while True:
        attempt += 1
        console.print(f"[green]Attempt {attempt}[/green]")
        reservation = backend_reserve(
            backend=backend,
            train_type=train_type,
            user=user,
            password=password,
            dep=dep,
            arr=arr,
            date=date,
            time=time,
            time_limit=time_limit,
            seat_priority=seat_priority,
            window=window_seat,
            standby=standby,
            try_waiting=try_waiting,
            counts=counts,
        )
        if reservation is not None:
            console.print(str(reservation))
            return
        if max_attempts and attempt >= max_attempts:
            console.print("[red]Max attempts reached[/red]")
            raise typer.Exit(code=1)
        time.sleep(poll_interval)


@app.command()
def reservations(
    backend: BackendType = typer.Option("auto", help="auto|srt|korail"),
    user: str = typer.Option(..., "--id", help="ID"),
    password: str = typer.Option(..., "--pw", help="Password"),
    train_type: str = typer.Option("srt", help="srt, ktx, all, etc."),
    paid_only: bool = typer.Option(False, help="SRT only: paid reservations"),
):
    resv = list_reservations(backend, train_type, user, password, paid_only)
    if not resv:
        console.print("[yellow]No reservations[/yellow]")
        return
    for r in resv:
        console.print(str(r))


@app.command()
def cancel(
    backend: BackendType = typer.Option("auto", help="auto|srt|korail"),
    user: str = typer.Option(..., "--id", help="ID"),
    password: str = typer.Option(..., "--pw", help="Password"),
    train_type: str = typer.Option("srt", help="srt, ktx, all, etc."),
    reservation_id: str = typer.Option(..., help="Reservation number"),
):
    ok = backend_cancel(backend, train_type, user, password, reservation_id)
    if ok:
        console.print("[green]Canceled[/green]")
    else:
        console.print("[red]Cancel failed[/red]")


if __name__ == "__main__":
    app()
