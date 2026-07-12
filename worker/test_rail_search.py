"""Unit tests for train search serialization helpers (no live carrier calls)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from worker.rail_search import (
    _duration_label,
    _duration_minutes,
    serialize_korail_train,
    serialize_srt_train,
)


class DurationTests(unittest.TestCase):
    def test_same_day(self) -> None:
        self.assertEqual(_duration_minutes("050300", "064600"), 103)
        self.assertEqual(_duration_label(103), "1시간 43분")

    def test_overnight(self) -> None:
        self.assertEqual(_duration_minutes("230000", "010000"), 120)


class SerializeTests(unittest.TestCase):
    def test_srt(self) -> None:
        train = SimpleNamespace(
            train_name="SRT",
            train_number="345",
            dep_station_name="수서",
            arr_station_name="대전",
            dep_date="20260718",
            dep_time="050300",
            arr_time="064600",
            general_seat_state="예약가능",
            special_seat_state="예약가능",
            general_seat_available=lambda: True,
            special_seat_available=lambda: True,
            seat_available=lambda: True,
        )
        row = serialize_srt_train(train)
        self.assertEqual(row["carrier"], "srt")
        self.assertEqual(row["dep_display"], "05:03")
        self.assertTrue(row["general"]["available"])

    def test_korail(self) -> None:
        train = SimpleNamespace(
            train_type_name="KTX",
            train_no="201",
            dep_name="서울",
            arr_name="동대구",
            dep_date="20260718",
            dep_time="050300",
            arr_time="064600",
            general_seat="11",
            special_seat="13",
            has_general_seat=lambda: True,
            has_special_seat=lambda: False,
            has_seat=lambda: True,
        )
        row = serialize_korail_train(train)
        self.assertEqual(row["train_number"], "201")
        self.assertTrue(row["general"]["available"])
        self.assertFalse(row["special"]["available"])


if __name__ == "__main__":
    unittest.main()
