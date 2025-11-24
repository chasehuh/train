from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator

ALLOWED_BACKENDS = {"auto", "srt", "korail"}
ALLOWED_TRAIN_TYPES = {
    "srt",
    "ktx",
    "ktx-sancheon",
    "saemaeul",
    "mugunghwa",
    "itx-saemaeul",
    "itx-cheongchun",
    "airport",
    "all",
}
ALLOWED_SEAT_PRIORITY = {
    "general-first",
    "general-only",
    "special-first",
    "special-only",
}
ALLOWED_WINDOW = {"window", "aisle", "any"}


class PassengerCountsModel(BaseModel):
    adult: int = 1
    child: int = 0
    senior: int = 0
    disability1: int = 0
    disability2: int = 0
    toddler: int = 0

    @field_validator("*")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Passenger count must be >= 0")
        return v


class BaseSearchModel(BaseModel):
    backend: str = "auto"
    user: str
    password: str
    dep: str
    arr: str
    date: Optional[str] = None
    time: Optional[str] = None
    time_limit: Optional[str] = None
    train_type: str = "srt"
    available_only: bool = True
    include_waiting: bool = False
    seat_priority: str = "general-first"
    window_seat: Optional[str] = None

    @field_validator("backend")
    @classmethod
    def backend_allowed(cls, v):
        if v not in ALLOWED_BACKENDS:
            raise ValueError(f"backend must be one of {ALLOWED_BACKENDS}")
        return v

    @field_validator("train_type")
    @classmethod
    def train_type_allowed(cls, v):
        if v.lower() not in ALLOWED_TRAIN_TYPES:
            raise ValueError(f"train_type must be one of {ALLOWED_TRAIN_TYPES}")
        return v

    @field_validator("seat_priority")
    @classmethod
    def seat_priority_allowed(cls, v):
        if v.lower() not in ALLOWED_SEAT_PRIORITY:
            raise ValueError(f"seat_priority must be one of {ALLOWED_SEAT_PRIORITY}")
        return v

    @field_validator("window_seat")
    @classmethod
    def window_allowed(cls, v):
        if v is None:
            return v
        if v.lower() not in ALLOWED_WINDOW:
            raise ValueError(f"window_seat must be one of {ALLOWED_WINDOW}")
        return v
