from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from srt_backend.seat_type import SeatType as SrtSeatType
from korail_backend.korail2 import ReserveOption as KorailSeatOption, TrainType as KorailTrainType


@dataclass
class PassengerCounts:
    adult: int = 1
    child: int = 0
    senior: int = 0
    disability1: int = 0
    disability2: int = 0
    toddler: int = 0  # korail only


def map_srt_seat_priority(name: str) -> SrtSeatType:
    mapping = {
        "general-first": SrtSeatType.GENERAL_FIRST,
        "general-only": SrtSeatType.GENERAL_ONLY,
        "special-first": SrtSeatType.SPECIAL_FIRST,
        "special-only": SrtSeatType.SPECIAL_ONLY,
    }
    return mapping.get(name.lower(), SrtSeatType.GENERAL_FIRST)


def map_korail_seat_option(name: str) -> KorailSeatOption:
    mapping = {
        "general-first": KorailSeatOption.GENERAL_FIRST,
        "general-only": KorailSeatOption.GENERAL_ONLY,
        "special-first": KorailSeatOption.SPECIAL_FIRST,
        "special-only": KorailSeatOption.SPECIAL_ONLY,
    }
    return mapping.get(name.lower(), KorailSeatOption.GENERAL_FIRST)


def map_korail_train_type(name: str) -> KorailTrainType:
    mapping = {
        "srt": KorailTrainType.ALL,  # SRT는 별도 백엔드에서 처리, AUTO 라우팅용
        "ktx": KorailTrainType.KTX,
        "ktx-sancheon": KorailTrainType.KTX_SANCHEON,
        "saemaeul": KorailTrainType.SAEMAEUL,
        "mugunghwa": KorailTrainType.MUGUNGHWA,
        "itx-saemaeul": KorailTrainType.ITX_SAEMAEUL,
        "itx-cheongchun": KorailTrainType.ITX_CHEONGCHUN,
        "airport": KorailTrainType.AIRPORT,
        "all": KorailTrainType.ALL,
    }
    return mapping.get(name.lower(), KorailTrainType.ALL)


def map_window_preference(window: Optional[str]) -> Optional[bool]:
    if window is None or window.lower() == "any":
        return None
    if window.lower() == "window":
        return True
    if window.lower() == "aisle":
        return False
    return None
