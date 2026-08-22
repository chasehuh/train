"""Operational helpers for Korail CLI commands."""

import logging
import os
import random
import sys
import time
from datetime import datetime
from typing import Iterable, Optional

import requests

from .korail2 import Korail, NeedToLoginError, NoResultsError, ReserveOption, SoldOutError

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

logger = logging.getLogger("monitor_and_reserve")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def normalize_id(raw_id: str) -> str:
    """Normalize phone-like IDs to ###-####-#### for Korail."""
    digits = "".join(ch for ch in raw_id if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return raw_id


def _load_env() -> None:
    if load_dotenv is None:
        return
    load_dotenv(override=False)


def _validate_time(dep_time: str) -> str:
    return datetime.strptime(dep_time, "%H%M%S").strftime("%H%M%S")


def _validate_date(dep_date: str) -> str:
    return datetime.strptime(dep_date, "%Y%m%d").strftime("%Y%m%d")


def prepare_trip(dep: str, arr: str, date: str, dep_time: str, end_time: Optional[str] = None):
    return {
        "dep": dep.strip(),
        "arr": arr.strip(),
        "date": _validate_date(date.strip()),
        "dep_time": _validate_time(dep_time.strip()),
        "end_time": _validate_time(end_time.strip()) if end_time else None,
    }


def load_credentials(args):
    _load_env()
    korail_id = normalize_id(getattr(args, "korail_id", None) or os.getenv("KORAIL_ID", ""))
    korail_pw = getattr(args, "korail_pw", None) or os.getenv("KORAIL_PW")
    if not korail_id or not korail_pw:
        raise RuntimeError(
            "Missing Korail credentials. Provide --id/--pw or set KORAIL_ID/KORAIL_PW in .env"
        )
    return korail_id, korail_pw


def resolve_notifications(args):
    token = getattr(args, "telegram_token", None) or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = getattr(args, "telegram_chat_id", None) or os.getenv("TELEGRAM_CHAT_ID")
    if getattr(args, "no_telegram", False):
        return None, None
    return token, chat_id


def create_client(args, auto_login=True):
    korail_id, korail_pw = load_credentials(args)
    korail = Korail(korail_id, korail_pw, auto_login=auto_login)
    if auto_login and not korail.logined:
        detail = ""
        if korail.last_login_error_message:
            detail = f" ({korail.last_login_error_code}: {korail.last_login_error_message})"
        raise RuntimeError(f"Login failed. Check credentials or Korail app compatibility.{detail}")
    return korail


def search_trains(
    korail: Korail,
    dep: str,
    arr: str,
    date: str,
    dep_time: str,
    end_time: Optional[str] = None,
    include_no_seats: bool = False,
    include_waiting_list: bool = False,
    limit: Optional[int] = None,
):
    trip = prepare_trip(dep, arr, date, dep_time, end_time)
    trains = korail.search_train(
        trip["dep"],
        trip["arr"],
        trip["date"],
        trip["dep_time"],
        include_no_seats=include_no_seats,
        include_waiting_list=include_waiting_list,
    )
    if trip["end_time"]:
        trains = [train for train in trains if train.dep_time <= trip["end_time"]]
    trains.sort(key=lambda train: (train.dep_date, train.dep_time, train.train_no))
    if limit is not None:
        trains = trains[: max(0, int(limit))]
    return trains


def print_trains(trains: Iterable) -> None:
    for index, train in enumerate(trains, start=1):
        print(f"{index}. {train}")


def print_reservations(reservations: Iterable) -> None:
    for index, reservation in enumerate(reservations, start=1):
        print(f"{index}. {reservation}")


def select_train(
    trains,
    exact: bool = False,
    dep: Optional[str] = None,
    arr: Optional[str] = None,
    date: Optional[str] = None,
    dep_time: Optional[str] = None,
    train_no: Optional[str] = None,
    require_general_seat: bool = True,
):
    candidates = list(trains)
    if dep:
        candidates = [train for train in candidates if train.dep_name == dep]
    if arr:
        candidates = [train for train in candidates if train.arr_name == arr]
    if date:
        candidates = [train for train in candidates if train.dep_date == date]
    if dep_time:
        if exact:
            candidates = [train for train in candidates if train.dep_time == dep_time]
        else:
            candidates = [train for train in candidates if train.dep_time >= dep_time]
    if train_no:
        candidates = [train for train in candidates if train.train_no == train_no]
    if require_general_seat:
        candidates = [train for train in candidates if train.has_general_seat()]
    if not candidates:
        raise NoResultsError()
    candidates.sort(key=lambda train: (train.dep_date, train.dep_time, train.train_no))
    return candidates[0]


def reserve_once(
    korail: Korail,
    dep: str,
    arr: str,
    date: str,
    dep_time: str,
    end_time: Optional[str] = None,
    exact: bool = False,
    train_no: Optional[str] = None,
):
    trip = prepare_trip(dep, arr, date, dep_time, end_time)
    trains = search_trains(
        korail,
        trip["dep"],
        trip["arr"],
        trip["date"],
        trip["dep_time"],
        end_time=trip["end_time"],
        include_no_seats=True,
        include_waiting_list=True,
    )
    train = select_train(
        trains,
        exact=exact,
        dep=trip["dep"],
        arr=trip["arr"],
        date=trip["date"],
        dep_time=trip["dep_time"],
        train_no=train_no,
        require_general_seat=True,
    )
    return korail.reserve(train, option=ReserveOption.GENERAL_ONLY)


def list_reservations(korail: Korail):
    return korail.reservations()


def cancel_reservation_by_id(korail: Korail, reservation_id: str):
    reservations = list_reservations(korail)
    for reservation in reservations:
        if reservation.rsv_id == reservation_id:
            korail.cancel(reservation)
            return reservation
    raise ValueError(f"Reservation not found: {reservation_id}")


def run_doctor(args):
    korail = create_client(args, auto_login=True)
    korail_id, _ = load_credentials(args)
    print("Korail CLI doctor")
    print(f"- login: ok")
    print(f"- normalized_id: {korail_id}")
    print(f"- user: {korail.name}")
    print(f"- membership: {korail.membership_number}")
    print(f"- version: {korail._version}")
    return korail


def poll_and_reserve(
    korail: Korail,
    dep: str,
    arr: str,
    date: str,
    dep_time: str,
    limit: int,
    interval: int,
    end_time: Optional[str] = None,
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    jitter: float = 0.0,
    monitor_only: bool = False,
):
    trip = prepare_trip(dep, arr, date, dep_time, end_time)
    interval = max(3, min(interval, 300))
    jitter = max(0.0, min(float(jitter), 5.0))
    last_snapshot = None
    attempt = 0
    relogin_attempts = 0

    while True:
        attempt += 1
        logger.info(
            "[%s] Searching %s->%s on %s from %s (limit %s)...",
            attempt,
            trip["dep"],
            trip["arr"],
            trip["date"],
            trip["dep_time"],
            limit,
        )
        try:
            trains = search_trains(
                korail,
                trip["dep"],
                trip["arr"],
                trip["date"],
                trip["dep_time"],
                end_time=trip["end_time"],
                include_no_seats=False,
                limit=limit,
            )
            trains = [train for train in trains if train.has_general_seat()]
            if not trains:
                raise NoResultsError()
            snapshot = tuple(
                f"{train.dep_date}-{train.dep_time}-{train.train_no}" for train in trains
            )
            if snapshot != last_snapshot:
                logger.info("Available trains changed: %s", trains)
                if monitor_only and telegram_token and telegram_chat_id:
                    lines = "\n".join(str(train) for train in trains)
                    _notify_telegram(
                        telegram_token,
                        telegram_chat_id,
                        f"Korail availability: {trip['dep']}->{trip['arr']} {trip['date']} from {trip['dep_time']}\n{lines}",
                    )
                last_snapshot = snapshot
            if monitor_only:
                _sleep_with_jitter(interval, jitter)
                continue
            for train in trains:
                logger.info("Trying %s", train)
                try:
                    reservation = korail.reserve(train, option=ReserveOption.GENERAL_ONLY)
                    logger.info(
                        "Reserved! ID=%s, train=%s",
                        getattr(reservation, "rsv_id", None),
                        reservation,
                    )
                    if telegram_token and telegram_chat_id:
                        _notify_telegram(
                            telegram_token,
                            telegram_chat_id,
                            f"Korail reserved: {trip['dep']}->{trip['arr']} {trip['date']} {train.dep_time}\n{reservation}",
                        )
                    return reservation
                except SoldOutError:
                    logger.info("Sold out while reserving candidate, moving on...")
                    continue
        except NoResultsError:
            logger.info("No seats found.")
        except NeedToLoginError:
            relogin_attempts += 1
            if relogin_attempts > 3:
                raise RuntimeError("Re-login failed too many times, aborting.")
            logger.info(
                "Session expired, re-authenticating (attempt %s)...",
                relogin_attempts,
            )
            if not korail.login():
                raise RuntimeError("Re-login failed, aborting.")
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected error: %s", exc)

        _sleep_with_jitter(interval, jitter)


def poll_and_reserve_exact_train(
    korail: Korail,
    dep: str,
    arr: str,
    date: str,
    exact_dep_time: str,
    interval: int,
    telegram_token: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
    jitter: float = 0.0,
    monitor_only: bool = False,
):
    trip = prepare_trip(dep, arr, date, exact_dep_time)
    interval = max(3, min(interval, 300))
    jitter = max(0.0, min(float(jitter), 5.0))
    last_available = None
    attempt = 0
    relogin_attempts = 0

    while True:
        attempt += 1
        logger.info(
            "[%s] Searching exact train %s->%s on %s at %s ...",
            attempt,
            trip["dep"],
            trip["arr"],
            trip["date"],
            trip["dep_time"],
        )
        try:
            trains = search_trains(
                korail,
                trip["dep"],
                trip["arr"],
                trip["date"],
                trip["dep_time"],
                include_no_seats=True,
                include_waiting_list=True,
            )
            train = select_train(
                trains,
                exact=True,
                dep=trip["dep"],
                arr=trip["arr"],
                date=trip["date"],
                dep_time=trip["dep_time"],
                require_general_seat=False,
            )
            logger.info("Found %s", train)
            if not train.has_general_seat():
                if last_available is not False:
                    logger.info("No general seats yet.")
                    last_available = False
                logger.info("No general seats yet, retrying...")
            else:
                if last_available is not True:
                    logger.info("General seat is available for %s", train)
                    if telegram_token and telegram_chat_id:
                        _notify_telegram(
                            telegram_token,
                            telegram_chat_id,
                            f"Korail availability: {trip['dep']}->{trip['arr']} {trip['date']} {trip['dep_time']}\n{train}",
                        )
                    last_available = True
                if monitor_only:
                    _sleep_with_jitter(interval, jitter)
                    continue
                reservation = korail.reserve(train, option=ReserveOption.GENERAL_ONLY)
                logger.info(
                    "Reserved! ID=%s, train=%s",
                    getattr(reservation, "rsv_id", None),
                    reservation,
                )
                if telegram_token and telegram_chat_id:
                    _notify_telegram(
                        telegram_token,
                        telegram_chat_id,
                        f"Korail reserved: {trip['dep']}->{trip['arr']} {trip['date']} {trip['dep_time']}\n{reservation}",
                    )
                return reservation
        except NoResultsError:
            logger.info("Exact train not found (or no schedule returned yet).")
        except NeedToLoginError:
            relogin_attempts += 1
            if relogin_attempts > 3:
                raise RuntimeError("Re-login failed too many times, aborting.")
            logger.info(
                "Session expired, re-authenticating (attempt %s)...",
                relogin_attempts,
            )
            if not korail.login():
                raise RuntimeError("Re-login failed, aborting.")
        except SoldOutError:
            logger.info("Sold out while reserving, retrying...")
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected error: %s", exc)

        _sleep_with_jitter(interval, jitter)


def _notify_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(
                "Telegram notify failed: %s %s",
                response.status_code,
                response.text[:200],
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Telegram notify error: %s", exc)


def _sleep_with_jitter(interval: int, jitter: float) -> None:
    sleep_for = float(interval)
    if jitter > 0:
        sleep_for += random.uniform(-jitter, jitter)
    time.sleep(max(0.1, sleep_for))


def main(argv=None):
    from .cli import main as cli_main
    return cli_main(sys.argv[1:] if argv is None else argv)
