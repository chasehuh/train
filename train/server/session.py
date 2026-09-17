"""Browser sessions for the web dashboard.

Credentials live only here, in process memory, for the life of the session:
idle TTL (default 30 min), absolute TTL (default 8 h), or until logout. Nothing is
written to disk, a database, logs, or job records. The Korail client object keeps
the password because each per-job sandbox needs it at create time.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from ..korail import normalize_id

IDLE_TTL_SEC = 30 * 60
ABSOLUTE_TTL_SEC = 8 * 60 * 60


class LoginError(Exception):
    def __init__(self, message: str, code: str | None = None, status: int = 401) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class RateLimited(LoginError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"too many login attempts, retry in {retry_after}s", "rate_limited", 429)
        self.retry_after = retry_after


def mask_id(korail_id: str) -> str:
    digits = "".join(c for c in korail_id if c.isdigit())
    if len(digits) >= 4:
        return "*" * (len(digits) - 4) + digits[-4:]
    return korail_id[:1] + "***"


@dataclass
class Session:
    id: str
    csrf: str
    client: Any  # korail2.Korail (logged in)
    created: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    @property
    def korail_id(self) -> str:
        return self.client.korail_id

    @property
    def masked_id(self) -> str:
        return mask_id(self.korail_id)

    @property
    def name(self) -> str | None:
        return getattr(self.client, "name", None)

    def credentials(self) -> dict[str, str]:
        return {"KORAIL_ID": self.client.korail_id, "KORAIL_PW": self.client.korail_pw}

    def expired(self, now: float | None = None) -> bool:
        now = now or time.time()
        return now - self.last_seen > IDLE_TTL_SEC or now - self.created > ABSOLUTE_TTL_SEC


class LoginRateLimiter:
    """Korail locks memberships after repeated bad passwords, so fail closed early:
    at most `max_failures` failed logins per key inside `window_sec`."""

    def __init__(self, max_failures: int = 5, window_sec: int = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_sec = window_sec
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, *keys: str) -> None:
        now = time.time()
        with self._lock:
            for key in keys:
                q = self._failures[key]
                while q and now - q[0] > self.window_sec:
                    q.popleft()
                if len(q) >= self.max_failures:
                    raise RateLimited(int(self.window_sec - (now - q[0])) + 1)

    def failed(self, *keys: str) -> None:
        now = time.time()
        with self._lock:
            for key in keys:
                self._failures[key].append(now)

    def succeeded(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)


def _korail_login(korail_id: str, korail_pw: str):
    from korail2 import Korail

    client = Korail(korail_id, korail_pw, auto_login=True)
    if not client.logined:
        raise LoginError(
            client.last_login_error_message or "Korail login failed",
            client.last_login_error_code,
        )
    return client


class SessionStore:
    def __init__(self, login: Callable[[str, str], Any] = _korail_login) -> None:
        self._login = login
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self.limiter = LoginRateLimiter()

    def create(self, korail_id: str, korail_pw: str, client_ip: str = "-") -> Session:
        korail_id = normalize_id(korail_id.strip())
        if not korail_id or not korail_pw:
            raise LoginError("id and password required", "missing", 422)
        keys = (f"ip:{client_ip}", f"id:{korail_id}")
        self.limiter.check(*keys)
        try:
            client = self._login(korail_id, korail_pw)
        except LoginError:
            self.limiter.failed(*keys)
            raise
        except Exception as exc:  # network / antibot / JSON errors from the Korail client
            self.limiter.failed(*keys)
            raise LoginError(f"Korail unreachable: {type(exc).__name__}", "upstream", 502) from exc
        self.limiter.succeeded(*keys)
        session = Session(id=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(24), client=client)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.expired():
                self._sessions.pop(session_id, None)
            else:
                session.last_seen = time.time()
                return session
        self._logout(session)
        return None

    def destroy(self, session_id: str | None) -> None:
        with self._lock:
            session = self._sessions.pop(session_id or "", None)
        if session:
            self._logout(session)

    def sweep(self) -> int:
        now = time.time()
        with self._lock:
            dead = [sid for sid, s in self._sessions.items() if s.expired(now)]
            gone = [self._sessions.pop(sid) for sid in dead]
        for session in gone:
            self._logout(session)
        return len(gone)

    def __len__(self) -> int:
        return len(self._sessions)

    @staticmethod
    def _logout(session: Session) -> None:
        try:
            session.client.logout()
        except Exception:  # best effort; the Korail session cookie dies with the object
            pass
        session.client.korail_pw = None
