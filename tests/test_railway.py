import json

import httpx
import pytest

from train.server.railway import Railway, RailwayError


def make(handler):
    return Railway(environment_id="env_1", token="tok", transport=httpx.MockTransport(handler))


def test_headers_project_token_vs_api_token():
    seen = {}

    def handler(request):
        seen.update(request.headers)
        return httpx.Response(200, json={"data": {"sandbox": None}})

    Railway(environment_id="e", project_token="p", transport=httpx.MockTransport(handler)).get_sandbox("x")
    assert seen["project-access-token"] == "p"
    Railway(environment_id="e", token="t", transport=httpx.MockTransport(handler)).get_sandbox("x")
    assert seen["authorization"] == "Bearer t"


def test_create_sandbox_payload_and_exec():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if "sandboxCreate" in body["query"]:
            return httpx.Response(200, json={"data": {"sandboxCreate": {"id": "sbx_1", "status": "CREATING"}}})
        if "sandboxExec" in body["query"]:
            return httpx.Response(200, json={"data": {"sandboxExec": {
                "exitCode": 0, "stdout": "hi\n", "stderr": "", "timedOut": False, "truncated": False}}})
        raise AssertionError(body["query"])

    rw = make(handler)
    box = rw.create_sandbox(variables={"KORAIL_ID": "x"}, template_name="train-abc", cpu=1, memory_gb=1)
    assert box["id"] == "sbx_1"
    inp = calls[0]["variables"]["input"]
    assert inp == {
        "environmentId": "env_1",
        "idleTimeoutMinutes": 30,
        "networkIsolation": "ISOLATED",
        "variables": {"KORAIL_ID": "x"},
        "template": {"name": "train-abc"},
        "resources": {"cpu": 1, "memoryGB": 1},
    }
    result = rw.exec("sbx_1", "echo hi", timeout_sec=5)
    assert result.exit_code == 0 and result.stdout == "hi\n"
    assert calls[1]["variables"] == {"e": "env_1", "id": "sbx_1", "c": "echo hi", "t": 5}


def test_graphql_errors_raise():
    rw = make(lambda r: httpx.Response(200, json={"errors": [{"message": "Not Authorized"}]}))
    with pytest.raises(RailwayError, match="Not Authorized"):
        rw.destroy_sandbox("sbx_1")
    rw = make(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(RailwayError, match="http 500"):
        rw.heartbeat("sbx_1")


def test_wait_running_polls_until_running(monkeypatch):
    statuses = iter(["CREATING", "CREATING", "RUNNING"])

    def handler(request):
        return httpx.Response(200, json={"data": {"sandbox": {"id": "sbx_1", "status": next(statuses)}}})

    rw = make(handler)
    assert rw.wait_running("sbx_1", poll_sec=0)["status"] == "RUNNING"

    rw = make(lambda r: httpx.Response(200, json={"data": {"sandbox": {"id": "sbx_1", "status": "FAILED"}}}))
    with pytest.raises(RailwayError, match="FAILED"):
        rw.wait_running("sbx_1", poll_sec=0)
