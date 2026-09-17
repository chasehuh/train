"""Job spec shared by the CLI, the HTTP API, and the worker command line."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), "KST")  # fixed offset: no DST in Korea, no tzdata needed on the worker image
SEAT_CLASSES = ("any", "general", "special")
MAX_MINUTES = 360
FIELDS = {
    "dep", "arr", "date", "time", "end_time", "trains", "seat_class",
    "seat_letter", "interval_sec", "monitor_only", "max_minutes",
}


def normalize_train_nos(raw: str | list[str] | None) -> list[str]:
    if not raw:
        return []
    items = raw.split(",") if isinstance(raw, str) else [str(n) for n in raw]
    return [n.strip().lstrip("0") or "0" for n in items if str(n).strip()]


def _strict(value: str, fmt: str, width: int, name: str, label: str) -> str:
    text = str(value).strip()
    if len(text) != width or not text.isdigit():
        raise ValueError(f"{name} must be {label}")
    try:
        return datetime.strptime(text, fmt).strftime(fmt)
    except ValueError:
        raise ValueError(f"{name} must be {label}") from None


def _hhmmss(value: str, name: str) -> str:
    return _strict(value, "%H%M%S", 6, name, "HHMMSS")


@dataclass(frozen=True)
class JobSpec:
    dep: str
    arr: str
    date: str
    time: str
    end_time: str | None = None
    trains: list[str] = field(default_factory=list)
    seat_class: str = "any"
    seat_letter: str | None = None
    interval_sec: float = 3.0
    monitor_only: bool = False
    max_minutes: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "JobSpec":
        if not isinstance(data, dict):
            raise ValueError("job must be an object")
        unknown = sorted(set(data) - FIELDS)
        if unknown:
            raise ValueError(f"unknown field(s): {', '.join(unknown)}")
        for key in ("dep", "arr", "date", "time"):
            if not str(data.get(key) or "").strip():
                raise ValueError(f"{key} is required")
        date = _strict(data["date"], "%Y%m%d", 8, "date", "YYYYMMDD")
        time = _hhmmss(data["time"], "time")
        end_time = _hhmmss(data["end_time"], "end_time") if data.get("end_time") else None
        if end_time and end_time < time:
            raise ValueError("end_time must not be before time")
        seat_class = str(data.get("seat_class") or "any")
        if seat_class not in SEAT_CLASSES:
            raise ValueError(f"seat_class must be one of {', '.join(SEAT_CLASSES)}")
        letter = None
        if data.get("seat_letter"):
            raw = str(data["seat_letter"]).strip().upper()
            if raw[-1] not in "ABCD" or (len(raw) > 1 and not raw[:-1].isdigit()):
                raise ValueError("seat_letter must be A, B, C or D")
            letter = raw[-1]
        try:
            interval = float(data.get("interval_sec", 3.0))
        except (TypeError, ValueError):
            raise ValueError("interval_sec must be a number") from None
        if interval < 0:
            raise ValueError("interval_sec must be >= 0")
        max_minutes = data.get("max_minutes")
        if max_minutes is not None:
            if not isinstance(max_minutes, int) or isinstance(max_minutes, bool):
                raise ValueError("max_minutes must be an integer")
            if not 1 <= max_minutes <= MAX_MINUTES:
                raise ValueError(f"max_minutes must be 1..{MAX_MINUTES}")
        monitor_only = data.get("monitor_only", False)
        if not isinstance(monitor_only, bool):
            raise ValueError("monitor_only must be a boolean")
        return cls(
            dep=str(data["dep"]).strip(),
            arr=str(data["arr"]).strip(),
            date=date,
            time=time,
            end_time=end_time,
            trains=normalize_train_nos(data.get("trains")),
            seat_class=seat_class,
            seat_letter=letter,
            interval_sec=interval,
            monitor_only=monitor_only,
            max_minutes=max_minutes,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def departure(self) -> datetime:
        """Departure as an aware datetime; Korail times are Korea Standard Time."""
        return datetime.strptime(self.date + self.time, "%Y%m%d%H%M%S").replace(tzinfo=KST)

    def budget_minutes(self, now: datetime | None = None) -> int:
        """Minutes a worker may run: explicit max_minutes, else until departure + 15.

        A naive `now` is taken as KST; the default is the current UTC time, so the
        result is the same on a laptop in Seoul and in a UTC container.
        """
        if self.max_minutes:
            return self.max_minutes
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=KST)
        until = self.departure() + timedelta(minutes=15) - now
        return max(1, min(MAX_MINUTES, int(until.total_seconds() // 60)))

    def to_argv(self) -> list[str]:
        argv = ["watch", "--dep", self.dep, "--arr", self.arr, "--date", self.date, "--time", self.time]
        if self.end_time:
            argv += ["--end-time", self.end_time]
        if self.trains:
            argv += ["--trains", ",".join(self.trains)]
        argv += ["--class", self.seat_class, "--interval", str(self.interval_sec)]
        if self.seat_letter:
            argv += ["--seat-letter", self.seat_letter]
        if self.monitor_only:
            argv.append("--monitor-only")
        argv += ["--max-minutes", str(self.budget_minutes())]
        return argv

    def to_shell(self) -> str:
        return shlex.join(self.to_argv())
