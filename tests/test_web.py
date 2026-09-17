"""Mocked end-to-end: login -> search -> reserve job -> hold -> cancel -> logout."""

import time

import pytest
from fastapi.testclient import TestClient

from korail2 import KorailError, SeatLetterMismatchError
from train.server.app import build_app
from train.server.jobs import JobRunner, Settings
from train.server.session import LoginError, SessionStore, mask_id
from tests.test_app import FakeRailway
from tests.test_watch import FakeTrain

GOOD = {"korail_id": "010-1234-5678", "korail_pw": "hunter2"}


class FakeReservation:
    def __init__(self, rsv_id, train_no="347", seat="3A"):
        self.rsv_id, self.train_no, self.seat_no, self.car_no = rsv_id, train_no, seat, "0005"
        self.train_type_name, self.dep_name, self.arr_name = "KTX", "수서", "동대구"
        self.dep_date, self.dep_time, self.arr_time = "20260918", "173000", "191200"
        self.seat_no_count, self.price = 1, 58900
        self.buy_limit_date, self.buy_limit_time = "20260917", "123000"


class FakeKorail:
    instances = []

    def __init__(self, korail_id, korail_pw):
        self.korail_id, self.korail_pw, self.name = korail_id, korail_pw, "허채원"
        self.logged_out = False
        self.holds = [FakeReservation("R1")]
        self.cancelled = []
        FakeKorail.instances.append(self)

    def search_train(self, dep, arr, date, time, include_no_seats=False):
        if dep == "없는역":
            raise KorailError("역 이름을 확인하세요", "WRR800029")
        t1 = FakeTrain("0347", dep="173000", special=True, general=False)
        t2 = FakeTrain("0351", dep="183000", special=False, general=True)
        for t in (t1, t2):
            t.train_type_name, t.dep_name, t.arr_name, t.dep_date, t.arr_time = "KTX", dep, arr, date, "191200"
            t.reserve_possible = "Y"
        return [t1, t2]

    def reservations(self, hydrate_seats=True):
        return list(self.holds)

    def cancel(self, rsv):
        self.holds = [h for h in self.holds if h.rsv_id != rsv.rsv_id]
        self.cancelled.append(rsv.rsv_id)
        return True

    def logout(self):
        self.logged_out = True


def fake_login(korail_id, korail_pw):
    if korail_pw != "hunter2":
        raise LoginError("비밀번호가 틀렸습니다", "WRC000101")
    return FakeKorail(korail_id, korail_pw)


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("INSECURE_COOKIES", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    rw = FakeRailway()
    runner = JobRunner(rw, Settings(poll_sec=3600))
    store = SessionStore(login=fake_login)
    client = TestClient(build_app(runner=runner, api_token="secret", sessions=store))
    FakeKorail.instances.clear()
    with client:
        yield rw, runner, store, client


def login(client, **over):
    r = client.post("/web/login", json={**GOOD, **over})
    return r


def test_e2e_login_search_job_hold_cancel_logout(env):
    rw, runner, store, client = env
    r = login(client)
    assert r.status_code == 200
    me = r.json()
    assert me["korail_id"] == "5678".rjust(11, "*") and me["name"] == "허채원" and me["csrf"]
    assert "korail_pw" not in r.text and "hunter2" not in r.text
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie.lower().replace("samesite=strict", "SameSite=strict")
    csrf = {"X-CSRF-Token": me["csrf"]}

    # search (CSRF required)
    body = {"dep": "수서", "arr": "동대구", "date": "20260918", "time": "170000"}
    assert client.post("/web/search", json=body).status_code == 403
    r = client.post("/web/search", json=body, headers=csrf)
    assert r.status_code == 200
    trains = r.json()["trains"]
    assert [t["train_no"] for t in trains] == ["347", "351"]
    assert trains[0]["special"] is True and trains[0]["general"] is False
    r = client.post("/web/search", json={**body, "end_time": "180000"}, headers=csrf)
    assert [t["train_no"] for t in r.json()["trains"]] == ["347"]
    r = client.post("/web/search", json={**body, "dep": "없는역"}, headers=csrf)
    assert r.status_code == 502 and "WRR800029" in r.json()["detail"]

    # reserve attempt -> job on a sandbox with the session credentials, never in the record
    job_body = {**body, "trains": ["347"], "seat_class": "special", "seat_letter": "A", "max_minutes": 10}
    r = client.post("/web/jobs", json=job_body, headers=csrf)
    assert r.status_code == 201
    job = r.json()
    assert job["owner"] == me["korail_id"] and "hunter2" not in r.text
    deadline = time.time() + 5
    while runner.get(job["id"]).status == "provisioning" and time.time() < deadline:
        time.sleep(0.01)
    sbx = runner.get(job["id"]).worker_id
    assert rw.boxes[sbx]["kw"]["variables"] == {
        "KORAIL_ID": "010-1234-5678", "KORAIL_PW": "hunter2", "TELEGRAM_BOT_TOKEN": "tg-token", "TELEGRAM_CHAT_ID": "42"}
    assert "hunter2" not in str(runner.get(job["id"]).to_dict())
    assert "--seat-letter A" in rw.files[sbx]["started"]

    # worker kept a hold
    rw.files[sbx]["exit"] = "0"
    rw.files[sbx]["log"] = "egress_ip=1.2.3.4\n[17:01:00] RESERVED KTX 347 5호 3A"
    runner.poll_once()
    r = client.get(f"/web/jobs/{job['id']}")
    assert r.json()["status"] == "reserved" and r.json()["egress_ip"] == "1.2.3.4"
    assert rw.destroyed == [sbx]

    # holds + cancel
    r = client.get("/web/holds")
    assert r.status_code == 200
    hold = r.json()["holds"][0]
    assert hold["rsv_id"] == "R1" and hold["car"] == "5" and hold["seat"] == "3A" and hold["price"] == 58900
    assert client.delete("/web/holds/R1").status_code == 403
    assert client.delete("/web/holds/nope", headers=csrf).status_code == 404
    assert client.delete("/web/holds/R1", headers=csrf).status_code == 200
    assert client.get("/web/holds").json()["holds"] == []

    # logout drops the server-side credentials
    korail = FakeKorail.instances[-1]
    assert client.post("/web/logout").status_code == 200
    assert korail.logged_out and korail.korail_pw is None
    assert client.get("/web/me").status_code == 401
    assert len(store) == 0


def test_bad_password_and_rate_limit(env):
    _, _, store, client = env
    r = login(client, korail_pw="wrong")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "WRC000101"
    for _ in range(4):
        assert login(client, korail_pw="wrong").status_code == 401
    r = login(client, korail_pw="wrong")
    assert r.status_code == 429 and r.headers["retry-after"]
    assert login(client).status_code == 429  # even the right password waits


def test_login_requires_json_and_bearer_api_still_works(env):
    _, _, _, client = env
    r = client.post("/web/login", data=GOOD)
    assert r.status_code in (415, 422)  # form posts never reach the login handler
    assert client.get("/jobs").status_code == 401
    assert client.get("/jobs", headers={"Authorization": "Bearer secret"}).status_code == 200


def test_session_expiry(env, monkeypatch):
    _, _, store, client = env
    assert login(client).status_code == 200
    assert client.get("/web/me").status_code == 200
    session = next(iter(store._sessions.values()))
    session.last_seen -= 31 * 60
    assert client.get("/web/me").status_code == 401
    assert FakeKorail.instances[-1].logged_out


def test_static_and_headers(env):
    _, _, _, client = env
    r = client.get("/")
    assert r.status_code == 200 and "코레일 로그인" in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'self'")
    assert r.headers["x-frame-options"] == "DENY"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/web/me").headers["cache-control"] == "no-store"
    assert client.get("/docs").status_code == 404


def test_mask_id():
    assert mask_id("010-1234-5678") == "*******5678"
    assert mask_id("chase@example.com") == "c***"
