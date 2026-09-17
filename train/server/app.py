"""FastAPI control plane + web dashboard. Run with: uvicorn train.server.app:app"""

from __future__ import annotations

import os
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from ..spec import JobSpec
from .jobs import JobRunner, Settings
from .railway import Railway
from .session import SessionStore
from .web import build_router

_bearer = HTTPBearer(auto_error=False)
STATIC = Path(__file__).parent / "static"

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
)


def build_app(
    runner: JobRunner | None = None,
    api_token: str | None = None,
    sessions: SessionStore | None = None,
) -> FastAPI:
    api_token = api_token if api_token is not None else os.environ.get("JOB_API_TOKEN", "")
    store = sessions if sessions is not None else SessionStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runner = runner or JobRunner(Railway(), Settings.from_env())
        app.state.runner.start()
        stop = threading.Event()

        def sweeper() -> None:
            while not stop.wait(60):
                store.sweep()

        threading.Thread(target=sweeper, daemon=True).start()
        yield
        stop.set()
        app.state.runner.stop()

    app = FastAPI(title="train", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.sessions = store

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith(("/web/", "/jobs")):
            response.headers["Cache-Control"] = "no-store"
        return response

    def auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
        if not api_token:
            raise HTTPException(503, "JOB_API_TOKEN not configured")
        if creds is None or not secrets.compare_digest(creds.credentials, api_token):
            raise HTTPException(401, "bad token")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    # -- bearer API (CLI / scripts) ------------------------------------------

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

    # -- web dashboard --------------------------------------------------------

    app.include_router(build_router(store))

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = build_app()
