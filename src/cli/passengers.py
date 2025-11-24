from __future__ import annotations

from srt_backend.passenger import (
    Adult as SrtAdult,
    Child as SrtChild,
    Disability1To3 as SrtDisability1To3,
    Disability4To6 as SrtDisability4To6,
    Senior as SrtSenior,
)
from korail_backend.korail2 import (
    AdultPassenger as KorailAdult,
    ChildPassenger as KorailChild,
    ToddlerPassenger as KorailToddler,
    SeniorPassenger as KorailSenior,
)

from .types import PassengerCounts


def build_srt_passengers(counts: PassengerCounts):
    passengers = []
    if counts.adult:
        passengers.append(SrtAdult(counts.adult))
    if counts.child:
        passengers.append(SrtChild(counts.child))
    if counts.senior:
        passengers.append(SrtSenior(counts.senior))
    if counts.disability1:
        passengers.append(SrtDisability1To3(counts.disability1))
    if counts.disability2:
        passengers.append(SrtDisability4To6(counts.disability2))
    return passengers or [SrtAdult(1)]


def build_korail_passengers(counts: PassengerCounts):
    passengers = []
    if counts.adult:
        passengers.append(KorailAdult(counts.adult))
    if counts.child:
        passengers.append(KorailChild(counts.child))
    if counts.toddler:
        passengers.append(KorailToddler(counts.toddler))
    if counts.senior:
        passengers.append(KorailSenior(counts.senior))
    return passengers or [KorailAdult(1)]
