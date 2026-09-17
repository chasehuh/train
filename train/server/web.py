"""Browser-facing routes: session login, search, reserve attempts, holds.

Security model
- Session id in an httpOnly, Secure, SameSite=Strict cookie; server-side store only.
- Every mutating route except login needs `X-CSRF-Token` equal to the session's token
  (handed out once at login / on GET /web/me, never in a cookie).
- Login is JSON-only (a cross-site form post cannot set application/json) and
  rate-limited per client IP and per Korail id.
- Reserve attempts never run here: they become jobs on per-job sandboxes; the
  session credentials are injected at sandbox create time only.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response

from ..spec import JobSpec, normalize_train_nos
from .session import LoginError, Session, SessionStore

COOKIE = "train_session"
CSRF_HEADER = "x-csrf-token"


def cookie_secure() -> bool:
    return os.environ.get("INSECURE_COOKIES") != "1"


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "-"


def build_router(store: SessionStore) -> APIRouter:
    router = APIRouter(prefix="/web")

    def current(request: Request) -> Session:
        session = store.get(request.cookies.get(COOKIE))
        if session is None:
            raise HTTPException(401, "login required")
        return session

    def mutating(request: Request, session: Session = Depends(current)) -> Session:
        if request.headers.get(CSRF_HEADER) != session.csrf:
            raise HTTPException(403, "bad csrf token")
        return session

    def korail_call(fn, *args, **kwargs):
        from korail2 import KorailError, NeedToLoginError, NoResultsError

        try:
            return fn(*args, **kwargs)
        except NoResultsError:
            return []
        except NeedToLoginError as exc:
            raise HTTPException(401, f"Korail session expired ({exc.code}); log in again")
        except KorailError as exc:
            raise HTTPException(502, f"Korail {exc.code}: {exc.msg}")
        except Exception as exc:  # noqa: BLE001 - surface transport errors plainly
            raise HTTPException(502, f"Korail unreachable: {type(exc).__name__}")

    def session_payload(session: Session) -> dict:
        return {"korail_id": session.masked_id, "name": session.name, "csrf": session.csrf}

    @router.post("/login")
    def login(request: Request, response: Response, body: dict = Body(...)) -> dict:
        if not request.headers.get("content-type", "").startswith("application/json"):
            raise HTTPException(415, "json only")
        try:
            session = store.create(
                str(body.get("korail_id") or ""), str(body.get("korail_pw") or ""), client_ip(request)
            )
        except LoginError as exc:
            headers = {"Retry-After": str(exc.retry_after)} if getattr(exc, "retry_after", None) else None
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}, headers=headers)
        response.set_cookie(
            COOKIE, session.id, max_age=8 * 60 * 60, httponly=True,
            secure=cookie_secure(), samesite="strict", path="/",
        )
        return session_payload(session)

    @router.get("/me")
    def me(session: Session = Depends(current)) -> dict:
        return session_payload(session)

    @router.post("/logout")
    def logout(request: Request, response: Response) -> dict:
        store.destroy(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @router.post("/search")
    def search(body: dict = Body(...), session: Session = Depends(mutating)) -> dict:
        try:
            spec = JobSpec.from_dict({k: body.get(k) for k in ("dep", "arr", "date", "time", "end_time") if body.get(k)})
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        nos = normalize_train_nos(body.get("trains"))
        trains = korail_call(
            session.client.search_train, spec.dep, spec.arr, spec.date, spec.time, include_no_seats=True
        )
        out = []
        for train in trains:
            no = str(train.train_no).lstrip("0")
            if nos and no not in nos:
                continue
            if spec.end_time and train.dep_time > spec.end_time:
                continue
            out.append(_train_dict(train))
        return {"trains": out}

    @router.post("/jobs", status_code=201)
    def create_job(request: Request, body: dict = Body(...), session: Session = Depends(mutating)) -> dict:
        try:
            spec = JobSpec.from_dict(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        runner = request.app.state.runner
        env = dict(session.credentials())
        for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            if os.environ.get(key):
                env[key] = os.environ[key]
        return runner.create(spec, worker_env=env, owner=session.masked_id).to_dict()

    @router.get("/jobs")
    def list_jobs(request: Request, session: Session = Depends(current)) -> list[dict]:
        return [j.to_dict() for j in request.app.state.runner.list()]

    @router.get("/jobs/{job_id}")
    def get_job(request: Request, job_id: str, session: Session = Depends(current)) -> dict:
        job = request.app.state.runner.get(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return job.to_dict()

    @router.delete("/jobs/{job_id}")
    def cancel_job(request: Request, job_id: str, session: Session = Depends(mutating)) -> dict:
        job = request.app.state.runner.cancel(job_id)
        if job is None:
            raise HTTPException(404, "no such job")
        return job.to_dict()

    @router.get("/holds")
    def holds(session: Session = Depends(current)) -> dict:
        items = korail_call(session.client.reservations)
        return {"holds": [_hold_dict(r) for r in items]}

    @router.delete("/holds/{rsv_id}")
    def cancel_hold(rsv_id: str, session: Session = Depends(mutating)) -> dict:
        items = korail_call(session.client.reservations, hydrate_seats=False)
        match = [r for r in items if r.rsv_id == rsv_id]
        if not match:
            raise HTTPException(404, "no such hold")
        korail_call(session.client.cancel, match[0])
        return {"ok": True, "rsv_id": rsv_id}

    return router


def _train_dict(train: Any) -> dict:
    return {
        "train_no": str(train.train_no).lstrip("0"),
        "train_type": train.train_type_name,
        "dep": train.dep_name,
        "arr": train.arr_name,
        "date": train.dep_date,
        "dep_time": train.dep_time,
        "arr_time": train.arr_time,
        "special": bool(train.has_special_seat()),
        "general": bool(train.has_general_seat()),
        "reserve_possible": train.reserve_possible == "Y",
    }


def _hold_dict(rsv: Any) -> dict:
    return {
        "rsv_id": rsv.rsv_id,
        "train_no": str(rsv.train_no).lstrip("0"),
        "train_type": rsv.train_type_name,
        "dep": rsv.dep_name,
        "arr": rsv.arr_name,
        "date": rsv.dep_date,
        "dep_time": rsv.dep_time,
        "arr_time": rsv.arr_time,
        "car": (str(rsv.car_no).lstrip("0") or None) if rsv.car_no else None,
        "seat": rsv.seat_no,
        "seats": rsv.seat_no_count,
        "price": rsv.price,
        "pay_by": f"{rsv.buy_limit_date} {rsv.buy_limit_time}",
    }
