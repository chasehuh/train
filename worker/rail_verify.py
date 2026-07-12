"""Probe SRT/Korail login for the rail-session verify endpoint."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

Carrier = Literal["srt", "korail"]


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    carrier: Carrier
    id_normalized: str
    id_masked: str
    error: str | None = None
    message: str | None = None


def normalize_rail_id(carrier: Carrier, raw_id: str) -> str:
    """Normalize membership / phone ids before login.

    Korail: 11-digit numbers starting with 01 stay hyphenated phones;
    other digit strings become digits-only membership (e.g. 075-232-8289 → 0752328289).
    SRT: keep phones hyphenated when 11 digits starting with 01; otherwise strip to digits
    when the input is digit/hyphen-only, else leave as-is (email membership).
    """
    user = (raw_id or "").strip()
    if not user:
        return user

    digits = "".join(ch for ch in user if ch.isdigit())
    if carrier == "korail":
        if len(digits) == 11 and digits.startswith("01"):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        if digits:
            return digits
        return user

    # srt
    if len(digits) == 11 and digits.startswith("01"):
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if digits and all(ch.isdigit() or ch == "-" for ch in user):
        return digits
    return user


def mask_rail_id(user_id: str) -> str:
    digits = "".join(ch for ch in user_id if ch.isdigit())
    if len(digits) >= 7:
        return f"{digits[:4]}****{digits[-3:]}"
    if len(user_id) <= 4:
        return "****"
    return f"{user_id[:2]}****{user_id[-2:]}"


def allow_env_creds() -> bool:
    import os

    return os.environ.get("ALLOW_ENV_CREDS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def verify_rail_login(carrier: Carrier, raw_id: str, password: str) -> VerifyResult:
    """Attempt a real carrier login. Never logs the password."""
    user = normalize_rail_id(carrier, raw_id)
    pw = password or ""
    if not user or not pw:
        return VerifyResult(
            ok=False,
            carrier=carrier,
            id_normalized=user,
            id_masked=mask_rail_id(user) if user else "****",
            error="validation_failed",
            message="id and password are required",
        )

    try:
        if carrier == "srt":
            from srt_backend import SRT

            # Constructor performs login; raises on failure.
            SRT(user, pw, verbose=False)
            return VerifyResult(
                ok=True,
                carrier=carrier,
                id_normalized=user,
                id_masked=mask_rail_id(user),
            )

        if carrier == "korail":
            from korail_backend.korail2 import Korail

            korail = Korail(user, pw, auto_login=True)
            if not korail.logined:
                return VerifyResult(
                    ok=False,
                    carrier=carrier,
                    id_normalized=user,
                    id_masked=mask_rail_id(user),
                    error="login_failed",
                    message="Korail login failed",
                )
            return VerifyResult(
                ok=True,
                carrier=carrier,
                id_normalized=user,
                id_masked=mask_rail_id(user),
            )

        return VerifyResult(
            ok=False,
            carrier=carrier,
            id_normalized=user,
            id_masked=mask_rail_id(user),
            error="validation_failed",
            message=f"unsupported carrier: {carrier}",
        )
    except Exception as exc:
        detail = str(exc).strip() or type(exc).__name__
        # Never echo the password if an upstream error string included it.
        if pw and pw in detail:
            detail = type(exc).__name__
        return VerifyResult(
            ok=False,
            carrier=carrier,
            id_normalized=user,
            id_masked=mask_rail_id(user),
            error="login_failed",
            message=f"{carrier} login failed: {detail}",
        )
