"""FastAPI control plane. Run with: uvicorn train.server.app:app"""

from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..spec import JobSpec
from .jobs import JobRunner, Settings
from .railway import Railway

_bearer = HTTPBearer(auto_error=False)


def build_app(runner: JobRunner | None = None, api_token: str | None = None) -> FastAPI:
    api_token = api_token if api_token is not None else os.environ.get("JOB_API_TOKEN", "")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runner = runner or JobRunner(Railway(), Settings.from_env())
        app.state.runner.start()
        yield
        app.state.runner.stop()

    app = FastAPI(title="train jobs", lifespan=lifespan)

    def auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
        if not api_token:
            raise HTTPException(503, "JOB_API_TOKEN not configured")
        if creds is None or not secrets.compare_digest(creds.credentials, api_token):
            raise HTTPException(401, "bad token")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.post("/jobs", status_code=201, dependencies=[Depends(auth)])
    def create_job(request: Request, body: dict = Body(...)) -> dict:
        try:
            spec = JobSpec.from_dict(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        return request.app.state.runner.create(spec).to_dict()

    @app.get("/jobs", dependencies=[Depends(auth)])
    def list_jobs(request: Request) -> list[dict]:
        return [job.to_dict() for job in request.app.state.runner.list()]

    @app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
    def get_job(request: Request, job_id: str) -> dict:
        job = request.app.state.runner.get(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return job.to_dict()

    @app.delete("/jobs/{job_id}", dependencies=[Depends(auth)])
    def delete_job(request: Request, job_id: str) -> dict:
        job = request.app.state.runner.cancel(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return job.to_dict()

    return app


app = build_app()
