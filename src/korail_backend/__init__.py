# -*- coding: utf-8 -*-
"""
    korail_backend
    ~~~~~~~~~~~~~~

    Vendored Korail client based on chasehuh/korail2 (carpedm20 + antibot).
"""

from .korail2 import (
    Korail,
    Passenger,
    AdultPassenger,
    ChildPassenger,
    ToddlerPassenger,
    SeniorPassenger,
    TrainType,
    ReserveOption,
)
from .korail2 import KorailError, NeedToLoginError, SoldOutError, NoResultsError

__all__ = [
    "Korail",
    "Passenger",
    "AdultPassenger",
    "ChildPassenger",
    "ToddlerPassenger",
    "SeniorPassenger",
    "TrainType",
    "ReserveOption",
    "KorailError",
    "NeedToLoginError",
    "SoldOutError",
    "NoResultsError",
]
