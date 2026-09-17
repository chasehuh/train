"""Thin client for the Railway public GraphQL API, sandbox operations only.

Field names come from live schema introspection (`railway api describe sandboxCreate`,
2026-09-17). Sandboxes are marked experimental by Railway; keep every field name here.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx

ENDPOINT = "https://backboard.railway.com/graphql/v2"

SANDBOX_FIELDS = "id status region environmentId idleTimeoutMinutes createdAt"


class RailwayError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    truncated: bool = False


class Railway:
    def __init__(
        self,
        environment_id: str | None = None,
        token: str | None = None,
        project_token: str | None = None,
        endpoint: str = ENDPOINT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.environment_id = environment_id or os.environ.get("RAILWAY_ENVIRONMENT_ID") or ""
        if not self.environment_id:
            raise RailwayError("RAILWAY_ENVIRONMENT_ID required")
        project_token = project_token or os.environ.get("RAILWAY_TOKEN")
        token = token or os.environ.get("RAILWAY_API_TOKEN")
        headers = {"Content-Type": "application/json"}
        if project_token:
            headers["Project-Access-Token"] = project_token
        elif token:
            headers["Authorization"] = f"Bearer {token}"
        else:
            raise RailwayError("RAILWAY_TOKEN (project token) or RAILWAY_API_TOKEN required")
        self._http = httpx.Client(
            base_url=endpoint, headers=headers, timeout=60.0, transport=transport
        )

    def _gql(self, query: str, variables: dict | None = None, timeout: float = 60.0) -> dict:
        response = self._http.post(
            "", json={"query": query, "variables": variables or {}}, timeout=timeout
        )
        if response.status_code != 200:
            raise RailwayError(f"railway http {response.status_code}: {response.text[:300]}")
        body = response.json()
        if body.get("errors"):
            raise RailwayError("; ".join(e.get("message", "?") for e in body["errors"]))
        return body.get("data") or {}

    # -- sandboxes -----------------------------------------------------------

    def create_sandbox(
        self,
        *,
        variables: dict[str, str] | None = None,
        idle_timeout_minutes: int = 30,
        template_name: str | None = None,
        region: str | None = None,
        cpu: float | None = None,
        memory_gb: float | None = None,
    ) -> dict:
        payload: dict = {
            "environmentId": self.environment_id,
            "idleTimeoutMinutes": idle_timeout_minutes,
            "networkIsolation": "ISOLATED",
            "variables": variables or {},
        }
        if template_name:
            payload["template"] = {"name": template_name}
        if region:
            payload["region"] = region
        if cpu or memory_gb:
            payload["resources"] = {"cpu": cpu, "memoryGB": memory_gb}
        data = self._gql(
            "mutation($input: SandboxCreateInput!) { sandboxCreate(input: $input) { %s } }"
            % SANDBOX_FIELDS,
            {"input": payload},
        )
        return data["sandboxCreate"]

    def get_sandbox(self, sandbox_id: str) -> dict | None:
        data = self._gql(
            "query($e: String!, $id: String!) { sandbox(environmentId: $e, id: $id) { %s } }"
            % SANDBOX_FIELDS,
            {"e": self.environment_id, "id": sandbox_id},
        )
        return data.get("sandbox")

    def list_sandboxes(self, active: bool = True) -> list[dict]:
        data = self._gql(
            "query($e: String!, $a: Boolean) { sandboxes(environmentId: $e, active: $a) "
            "{ edges { node { %s } } } }" % SANDBOX_FIELDS,
            {"e": self.environment_id, "a": active},
        )
        return [edge["node"] for edge in data["sandboxes"]["edges"]]

    def wait_running(self, sandbox_id: str, timeout_sec: float = 180, poll_sec: float = 2) -> dict:
        end = time.time() + timeout_sec
        while True:
            box = self.get_sandbox(sandbox_id)
            status = (box or {}).get("status")
            if status == "RUNNING":
                return box
            if status in (None, "FAILED", "DESTROYING", "DESTROYED"):
                raise RailwayError(f"sandbox {sandbox_id} is {status}")
            if time.time() >= end:
                raise RailwayError(f"sandbox {sandbox_id} still {status} after {timeout_sec}s")
            time.sleep(poll_sec)

    def exec(self, sandbox_id: str, command: str, timeout_sec: int = 60) -> ExecResult:
        data = self._gql(
            "mutation($e: String!, $id: String!, $c: String!, $t: Int) "
            "{ sandboxExec(environmentId: $e, id: $id, command: $c, timeoutSec: $t) "
            "{ exitCode stdout stderr timedOut truncated } }",
            {"e": self.environment_id, "id": sandbox_id, "c": command, "t": timeout_sec},
            timeout=timeout_sec + 30,
        )
        r = data["sandboxExec"]
        return ExecResult(r["exitCode"], r["stdout"], r["stderr"], r["timedOut"], r["truncated"])

    def destroy_sandbox(self, sandbox_id: str) -> None:
        self._gql(
            "mutation($e: String!, $id: String!) { sandboxDestroy(environmentId: $e, id: $id) { id } }",
            {"e": self.environment_id, "id": sandbox_id},
        )

    def heartbeat(self, sandbox_id: str) -> None:
        self._gql(
            "mutation($e: String!, $id: String!) { sandboxHeartbeat(environmentId: $e, id: $id) { id } }",
            {"e": self.environment_id, "id": sandbox_id},
        )

    # -- checkpoints / templates --------------------------------------------

    def create_checkpoint(self, sandbox_id: str, name: str) -> dict:
        data = self._gql(
            "mutation($e: String!, $id: String!, $n: String!) "
            "{ sandboxCheckpointCreate(environmentId: $e, sandboxId: $id, name: $n) { id key createdAt } }",
            {"e": self.environment_id, "id": sandbox_id, "n": name},
            timeout=300,
        )
        return data["sandboxCheckpointCreate"]

    def list_checkpoints(self) -> list[dict]:
        data = self._gql(
            "query($e: String!) { sandboxCheckpoints(environmentId: $e) { id key createdAt } }",
            {"e": self.environment_id},
        )
        return data["sandboxCheckpoints"]

    def build_template(
        self, instructions: list[str], variables: dict[str, str] | None = None, region: str | None = None
    ) -> dict:
        payload: dict = {"instructions": instructions, "variables": variables or {}}
        if region:
            payload["region"] = region
        data = self._gql(
            "mutation($e: String!, $input: SandboxTemplateInput!) "
            "{ sandboxTemplateBuild(environmentId: $e, input: $input) { id status } }",
            {"e": self.environment_id, "input": payload},
            timeout=600,
        )
        return data["sandboxTemplateBuild"]

    def template_build(self, build_id: str) -> dict:
        data = self._gql(
            "query($e: String!, $id: ID!) { sandboxTemplateBuild(environmentId: $e, id: $id) { id status } }",
            {"e": self.environment_id, "id": build_id},
        )
        return data["sandboxTemplateBuild"]
