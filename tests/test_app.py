import json
import time

from fastapi.testclient import TestClient

from train.server.app import build_app
from train.server.jobs import JobRunner, Settings, parse_status, start_script, status_for_exit
from train.server.railway import ExecResult, RailwayError
from train.spec import JobSpec

BODY = {"dep": "수서", "arr": "동대구", "date": "20260918", "time": "173000",
        "trains": ["347"], "seat_class": "special", "seat_letter": "A", "monitor_only": True}


class FakeRailway:
    """In-memory stand-in for train.server.railway.Railway."""

    def __init__(self):
        self.boxes = {}
        self.files = {}
        self.destroyed = []
        self.heartbeats = []
        self.n = 0

    def create_sandbox(self, **kw):
        self.n += 1
        sid = f"sbx_{self.n}"
        self.boxes[sid] = {"id": sid, "status": "RUNNING", "kw": kw}
        return dict(self.boxes[sid])

    def wait_running(self, sid, **kw):
        return self.boxes[sid]

    def get_sandbox(self, sid):
        return self.boxes.get(sid)

    def list_sandboxes(self, active=True):
        return [b for b in self.boxes.values() if b["status"] == "RUNNING"]

    def exec(self, sid, command, timeout_sec=60):
        if sid not in self.boxes or self.boxes[sid]["status"] != "RUNNING":
            raise RailwayError("not running")
        if "spec.json" in command and "run.sh" in command:
            self.files.setdefault(sid, {})["started"] = command
            return ExecResult(0, "started\n", "")
        if command.startswith("cat /job/spec.json"):
            return ExecResult(0, self.files.get(sid, {}).get("spec", ""), "")
        exit_code = self.files.get(sid, {}).get("exit", "")
        log = self.files.get(sid, {}).get("log", "")
        return ExecResult(0, f"{exit_code}\n__TRAIN_SEP__\n{log}", "")

    def destroy_sandbox(self, sid):
        self.destroyed.append(sid)
        self.boxes[sid]["status"] = "DESTROYED"

    def heartbeat(self, sid):
        self.heartbeats.append(sid)


def make():
    rw = FakeRailway()
    runner = JobRunner(rw, Settings(worker_env={"KORAIL_ID": "u", "KORAIL_PW": "p"}, poll_sec=3600))
    client = TestClient(build_app(runner=runner, api_token="secret"))
    return rw, runner, client


def wait_status(runner, job_id, status, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if runner.get(job_id).status == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"job never reached {status}: {runner.get(job_id).status}")


def test_auth_required():
    _, _, client = make()
    with client:
        assert client.get("/jobs").status_code == 401
        assert client.get("/jobs", headers={"Authorization": "Bearer nope"}).status_code == 401
        assert client.get("/healthz").status_code == 200


def test_job_lifecycle_two_jobs_two_sandboxes():
    rw, runner, client = make()
    h = {"Authorization": "Bearer secret"}
    with client:
        a = client.post("/jobs", json=BODY, headers=h).json()
        b = client.post("/jobs", json={**BODY, "trains": ["351"]}, headers=h).json()
        assert a["status"] in ("provisioning", "running") and a["worker_kind"] == "railway_sandbox"
        wait_status(runner, a["id"], "running")
        wait_status(runner, b["id"], "running")
        a, b = client.get(f"/jobs/{a['id']}", headers=h).json(), client.get(f"/jobs/{b['id']}", headers=h).json()
        assert {a["worker_id"], b["worker_id"]} == {"sbx_1", "sbx_2"}
        assert rw.boxes["sbx_1"]["kw"]["variables"] == {"KORAIL_ID": "u", "KORAIL_PW": "p"}
        assert rw.boxes["sbx_1"]["kw"]["idle_timeout_minutes"] == 30
        assert "--monitor-only" in rw.files["sbx_1"]["started"]
        assert "python3 -m train watch" in rw.files["sbx_1"]["started"]

        # worker A finished with a kept hold; B still polling
        rw.files["sbx_1"]["exit"] = "0"
        rw.files["sbx_1"]["log"] = "egress_ip=1.2.3.4\n[12:00:00] RESERVED x"
        rw.files["sbx_2"]["log"] = "egress_ip=5.6.7.8\n[12:00:00] #3 347=특X/일X"
        runner.poll_once()
        a = client.get(f"/jobs/{a['id']}", headers=h).json()
        assert a["status"] == "idle_timeout"  # monitor_only exit 0 is not a hold
        assert a["egress_ip"] == "1.2.3.4" and "RESERVED" in a["log_tail"]
        assert rw.destroyed == ["sbx_1"]
        b = client.get(f"/jobs/{b['id']}", headers=h).json()
        assert b["status"] == "running" and b["egress_ip"] == "5.6.7.8"

        # cancel B: destroy + terminal
        b = client.delete(f"/jobs/{b['id']}", headers=h).json()
        assert b["status"] == "cancelled" and rw.destroyed == ["sbx_1", "sbx_2"]
        assert client.delete("/jobs/nope", headers=h).status_code == 404
        assert len(client.get("/jobs", headers=h).json()) == 2


def test_validation_errors_are_422():
    _, _, client = make()
    h = {"Authorization": "Bearer secret"}
    with client:
        r = client.post("/jobs", json={**BODY, "carrier": "srt"}, headers=h)
        assert r.status_code == 422 and "carrier" in r.json()["detail"]
        r = client.post("/jobs", json={**BODY, "seat_letter": "E"}, headers=h)
        assert r.status_code == 422


def test_sandbox_vanished_marks_idle_timeout():
    rw, runner, client = make()
    with client:
        job = runner.create(JobSpec.from_dict(BODY))
        wait_status(runner, job.id, "running")
        rw.boxes[job.worker_id]["status"] = "DESTROYED"
        runner.poll_once()
        assert job.status == "idle_timeout"
        assert rw.destroyed == []


def test_reconcile_adopts_sandbox_with_spec():
    rw = FakeRailway()
    sid = rw.create_sandbox()["id"]
    rw.files[sid] = {"spec": '{"job_id": "job_old", "spec": %s, "created_at": "2026-09-18T08:00:00Z"}'
                     % json.dumps(BODY, ensure_ascii=False)}
    rw.create_sandbox()  # someone else's sandbox, no spec.json
    runner = JobRunner(rw, Settings(poll_sec=3600))
    runner.reconcile()
    assert list(runner.jobs) == ["job_old"]
    assert runner.jobs["job_old"].worker_id == sid
    assert runner.jobs["job_old"].status == "running"


def test_cancel_during_provisioning_destroys_the_sandbox():
    rw = FakeRailway()
    runner = JobRunner(rw, Settings(poll_sec=3600))
    job = runner.create(JobSpec.from_dict(BODY))
    runner.cancel(job.id)  # may race the provisioning thread either way
    wait_status(runner, job.id, "cancelled")
    end = time.time() + 5
    while time.time() < end and not rw.destroyed and rw.boxes:
        time.sleep(0.01)
    assert job.status == "cancelled"
    assert all(b["status"] == "DESTROYED" for b in rw.boxes.values())


def test_status_helpers():
    spec = JobSpec.from_dict(BODY)
    assert status_for_exit(0, JobSpec.from_dict({**BODY, "monitor_only": False})) == "reserved"
    assert status_for_exit(0, spec) == "idle_timeout"
    assert status_for_exit(3, spec) == "idle_timeout"
    assert status_for_exit(1, spec) == "failed"
    assert parse_status("\n__TRAIN_SEP__\negress_ip=9.9.9.9\nline") == (None, "egress_ip=9.9.9.9\nline", "9.9.9.9")
    assert parse_status("3\n__TRAIN_SEP__\n")[0] == 3
    script = start_script("job_x", spec)
    assert "/job/spec.json" in script and "--seat-letter A" in script and "setsid nohup" in script
