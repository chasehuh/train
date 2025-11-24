from __future__ import annotations

from typing import Optional

from korail_backend.korail2 import (
    Korail,
    ReserveOption,
    Train,
    TrainType,
    Reservation as KorailReservation,
    NoResultsError,
    SoldOutError,
)

from .passengers import build_korail_passengers
from .types import PassengerCounts, map_korail_seat_option, map_korail_train_type


def search(
    user: str,
    password: str,
    dep: str,
    arr: str,
    date: Optional[str],
    time: Optional[str],
    train_type: TrainType,
    counts: PassengerCounts,
    include_no_seats: bool,
    include_waiting: bool,
):
    client = Korail(user, password, auto_login=True)
    passengers = build_korail_passengers(counts)
    trains = client.search_train(
        dep,
        arr,
        date=date,
        time=time,
        train_type=train_type,
        passengers=passengers,
        include_no_seats=include_no_seats,
        include_waiting_list=include_waiting,
    )
    return trains


def reserve(
    user: str,
    password: str,
    train: Train,
    counts: PassengerCounts,
    seat_priority: str,
    try_waiting: bool,
):
    client = Korail(user, password, auto_login=True)
    passengers = build_korail_passengers(counts)
    option = map_korail_seat_option(seat_priority)
    return client.reserve(train, passengers=passengers, option=option, try_waiting=try_waiting)


def list_reservations(user: str, password: str):
    client = Korail(user, password, auto_login=True)
    return client.reservations()


def cancel(user: str, password: str, reservation_id: str):
    client = Korail(user, password, auto_login=True)
    # Korail cancel requires Reservation object; construct minimal stub.
    dummy = KorailReservation(
        {
            "h_pnr_no": reservation_id,
            "h_trn_clsf_cd": "00",
            "h_trn_clsf_nm": "",
            "h_trn_gp_cd": "109",
            "h_trn_no": "",
            "h_dpt_rs_stn_nm": "",
            "h_dpt_rs_stn_cd": "",
            "h_dpt_dt": "",
            "h_dpt_tm": "",
            "h_arv_rs_stn_nm": "",
            "h_arv_rs_stn_cd": "",
            "h_arv_dt": "",
            "h_arv_tm": "",
            "h_run_dt": "",
            "h_rsv_psb_flg": "",
            "h_rsv_psb_nm": "",
            "h_spe_rsv_cd": "",
            "h_gen_rsv_cd": "",
            "h_wait_rsv_flg": "",
            "h_tot_seat_cnt": "1",
            "h_ntisu_lmt_dt": "",
            "h_ntisu_lmt_tm": "",
            "h_rsv_amt": "0",
        }
    )
    return client.cancel(dummy)
