import pytest

from train.spec import JobSpec, normalize_train_nos

BASE = {"dep": "수서", "arr": "동대구", "date": "20260918", "time": "173000"}


def test_minimal_spec_defaults():
    spec = JobSpec.from_dict(BASE)
    assert spec.seat_class == "any"
    assert spec.trains == []
    assert spec.interval_sec == 3.0
    assert spec.monitor_only is False
    assert spec.seat_letter is None


def test_full_spec_and_argv_roundtrip():
    spec = JobSpec.from_dict(
        {
            **BASE,
            "end_time": "183000",
            "trains": ["0347", "351"],
            "seat_class": "special",
            "seat_letter": "12a",
            "interval_sec": 2,
            "monitor_only": True,
            "max_minutes": 30,
        }
    )
    assert spec.trains == ["347", "351"]
    assert spec.seat_letter == "A"
    argv = spec.to_argv()
    assert argv[:3] == ["watch", "--dep", "수서"]
    assert "--monitor-only" in argv
    assert argv[argv.index("--trains") + 1] == "347,351"
    assert argv[argv.index("--max-minutes") + 1] == "30"
    assert JobSpec.from_dict(spec.to_dict()) == spec


def test_normalize_train_nos():
    assert normalize_train_nos("0347, 351,,0") == ["347", "351", "0"]
    assert normalize_train_nos(None) == []


@pytest.mark.parametrize(
    "patch, message",
    [
        ({"dep": ""}, "dep is required"),
        ({"date": "2026-09-18"}, "date must be YYYYMMDD"),
        ({"time": "1730"}, "time must be HHMMSS"),
        ({"end_time": "170000"}, "end_time must not be before"),
        ({"seat_class": "first"}, "seat_class must be"),
        ({"seat_letter": "E"}, "seat_letter must be"),
        ({"seat_letter": "AB"}, "seat_letter must be"),
        ({"interval_sec": "fast"}, "interval_sec must be a number"),
        ({"max_minutes": 0}, "max_minutes must be 1"),
        ({"max_minutes": "30"}, "max_minutes must be an integer"),
        ({"monitor_only": "yes"}, "monitor_only must be a boolean"),
        ({"carrier": "srt"}, r"unknown field\(s\): carrier"),
        ({"korail_pw": "x"}, r"unknown field\(s\): korail_pw"),
    ],
)
def test_invalid_specs(patch, message):
    with pytest.raises(ValueError, match=message):
        JobSpec.from_dict({**BASE, **patch})


def test_budget_minutes_until_departure():
    from datetime import datetime

    spec = JobSpec.from_dict(BASE)
    now = datetime(2026, 9, 18, 17, 0, 0)
    assert spec.budget_minutes(now) == 45  # 30 min to departure + 15 grace
    assert spec.budget_minutes(datetime(2026, 9, 19)) == 1
    assert JobSpec.from_dict({**BASE, "max_minutes": 7}).budget_minutes(now) == 7
