import time

from korail2 import SeatLetterMismatchError
from train.korail import EXIT_DEADLINE, EXIT_FAILED, EXIT_RESERVED, watch
from train.spec import JobSpec


class FakeTrain:
    def __init__(self, no, dep="173000", special=True, general=False):
        self.train_no, self.dep_time, self._sp, self._gen = no, dep, special, general

    def has_special_seat(self):
        return self._sp

    def has_general_seat(self):
        return self._gen

    def __repr__(self):
        return f"Train {self.train_no}"


class FakeKorail:
    def __init__(self, trains, reserve_results):
        self.trains = trains
        self.reserve_results = list(reserve_results)
        self.reserve_calls = []
        self.searches = 0

    def search_train(self, *args, **kwargs):
        self.searches += 1
        return self.trains

    def reserve(self, train, option=None, seat_letter=None):
        self.reserve_calls.append((train.train_no, option, seat_letter))
        result = self.reserve_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def spec(**over):
    return JobSpec.from_dict(
        {"dep": "수서", "arr": "동대구", "date": "20260918", "time": "170000",
         "interval_sec": 0, "seat_class": "special", **over}
    )


def test_wrong_letter_is_cancelled_then_retried(capsys):
    client = FakeKorail(
        [FakeTrain("0347")],
        [SeatLetterMismatchError("3B", "A"), "RSV-OK"],
    )
    code = watch(client=client, spec=spec(seat_letter="A", trains="347"), telegram=(None, None))
    assert code == EXIT_RESERVED
    assert [c[2] for c in client.reserve_calls] == ["A", "A"]
    out = capsys.readouterr().out
    assert "wrong letter 3B, wanted A; cancelled" in out
    assert "RESERVED RSV-OK" in out


def test_one_shot_reserve_gives_up_after_one_attempt():
    client = FakeKorail([FakeTrain("347")], [SeatLetterMismatchError("3B", "A")])
    code = watch(client=client, spec=spec(seat_letter="A"), telegram=(None, None), max_attempts=1)
    assert code == EXIT_FAILED
    assert client.searches == 1


def test_monitor_only_never_reserves_and_stops_at_deadline():
    client = FakeKorail([FakeTrain("347")], [])
    code = watch(
        client=client,
        spec=spec(monitor_only=True),
        telegram=(None, None),
        deadline=time.time() + 0.05,
    )
    assert code == EXIT_DEADLINE
    assert client.reserve_calls == []
    assert client.searches >= 1


def test_train_filter_and_end_time():
    late = FakeTrain("351", dep="190000")
    wanted = FakeTrain("349", dep="180000")
    client = FakeKorail([late, wanted], ["RSV"])
    code = watch(
        client=client,
        spec=spec(end_time="183000", trains=["351", "349"]),
        telegram=(None, None),
        max_attempts=1,
    )
    assert code == EXIT_RESERVED
    assert client.reserve_calls[0][0] == "349"
