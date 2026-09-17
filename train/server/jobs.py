"""Job registry + per-job sandbox lifecycle (provision, poll, reap)."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..korail import EXIT_DEADLINE, EXIT_RESERVED
from ..spec import JobSpec
from .railway import Railway, RailwayError

TERMINAL = {"reserved", "idle_timeout", "cancelled", "failed"}
WORKER_ENV_KEYS = ("KORAIL_ID", "KORAIL_PW", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
JOB_DIR = "/job"
SEP = "__TRAIN_SEP__"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z") if dt else None


@dataclass
class Settings:
    template_name: str | None = None
    region: str | None = None
    idle_timeout_minutes: int = 30
    cpu: float | None = 1.0
    memory_gb: float | None = 1.0
    worker_env: dict[str, str] = field(default_factory=dict)
    poll_sec: float = 30.0
    heartbeat_sec: float = 300.0
    grace_minutes: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            template_name=env.get("WORKER_TEMPLATE") or None,
            region=env.get("WORKER_REGION") or None,
            idle_timeout_minutes=int(env.get("WORKER_IDLE_TIMEOUT_MINUTES", "30")),
            cpu=float(env["WORKER_CPU"]) if env.get("WORKER_CPU") else 1.0,
            memory_gb=float(env["WORKER_MEMORY_GB"]) if env.get("WORKER_MEMORY_GB") else 1.0,
            worker_env={k: env[k] for k in WORKER_ENV_KEYS if env.get(k)},
            poll_sec=float(env.get("JOB_POLL_SEC", "30")),
        )


@dataclass
class Job:
    id: str
    spec: JobSpec
    status: str = "provisioning"
    worker_kind: str = "railway_sandbox"
    worker_id: str | None = None
    egress_ip: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    deadline_at: datetime | None = None
    last_heartbeat: float = 0.0
    log_tail: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "worker_kind": self.worker_kind,
            "worker_id": self.worker_id,
            "egress_ip": self.egress_ip,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "deadline_at": _iso(self.deadline_at),
            "spec": self.spec.to_dict(),
            "log_tail": self.log_tail,
            "error": self.error,
        }


def start_script(job_id: str, spec: JobSpec) -> str:
    """Shell that writes the spec, then detaches the watch loop and returns."""
    return f"""set -e
mkdir -p {JOB_DIR}
cat > {JOB_DIR}/spec.json <<'__SPEC__'
{json.dumps({"job_id": job_id, "spec": spec.to_dict(), "created_at": _iso(_now())}, ensure_ascii=False)}
__SPEC__
cat > {JOB_DIR}/run.sh <<'__RUN__'
#!/bin/bash -l
echo "egress_ip=$(curl -s --max-time 10 https://api.ipify.org || echo unknown)"
python3 -m train {spec.to_shell()}
echo $? > {JOB_DIR}/exit
__RUN__
chmod +x {JOB_DIR}/run.sh
setsid nohup {JOB_DIR}/run.sh > {JOB_DIR}/log 2>&1 < /dev/null &
echo started
"""


STATUS_SCRIPT = f"cat {JOB_DIR}/exit 2>/dev/null; echo {SEP}; tail -n 40 {JOB_DIR}/log 2>/dev/null"


def parse_status(stdout: str) -> tuple[int | None, str, str | None]:
    """Returns (exit_code or None, log tail, egress ip or None)."""
    head, _, tail = stdout.partition(SEP)
    code = int(head.strip()) if head.strip().lstrip("-").isdigit() else None
    ip = None
    for line in tail.splitlines():
        if line.startswith("egress_ip="):
            ip = line.split("=", 1)[1].strip() or None
            break
    return code, tail.strip(), ip


def status_for_exit(code: int, spec: JobSpec) -> str:
    if code == EXIT_RESERVED and not spec.monitor_only:
        return "reserved"
    if code in (EXIT_RESERVED, EXIT_DEADLINE):
        return "idle_timeout"
    return "failed"


class JobRunner:
    def __init__(self, railway: Railway, settings: Settings) -> None:
        self.railway = railway
        self.settings = settings
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- public --------------------------------------------------------------

    def create(self, spec: JobSpec) -> Job:
        job = Job(id="job_" + secrets.token_hex(4), spec=spec)
        with self._lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._provision, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel(self, job_id: str) -> Job | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        if job.status in TERMINAL:
            return job
        self._finish(job, "cancelled")
        return job

    def start(self) -> None:
        self.reconcile()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # -- lifecycle -----------------------------------------------------------

    def _provision(self, job: Job) -> None:
        s = self.settings
        try:
            box = self.railway.create_sandbox(
                variables=s.worker_env,
                idle_timeout_minutes=s.idle_timeout_minutes,
                template_name=s.template_name,
                region=s.region,
                cpu=s.cpu,
                memory_gb=s.memory_gb,
            )
            job.worker_id = box["id"]
            job.updated_at = _now()
            self.railway.wait_running(box["id"])
            result = self.railway.exec(box["id"], start_script(job.id, job.spec), timeout_sec=60)
            if result.exit_code != 0 or "started" not in result.stdout:
                raise RailwayError(f"worker start failed: {result.stderr[-300:] or result.stdout[-300:]}")
            job.deadline_at = _now() + timedelta(minutes=job.spec.budget_minutes() + s.grace_minutes)
            job.last_heartbeat = time.time()
            job.status = "running"
            job.updated_at = _now()
        except Exception as exc:  # noqa: BLE001 - surface any provisioning failure on the job
            job.error = f"{type(exc).__name__}: {exc}"
            self._finish(job, "failed")

    def _finish(self, job: Job, status: str) -> None:
        if job.worker_id:
            try:
                result = self.railway.exec(job.worker_id, STATUS_SCRIPT, timeout_sec=20)
                _, tail, ip = parse_status(result.stdout)
                job.log_tail = tail or job.log_tail
                job.egress_ip = job.egress_ip or ip
            except RailwayError:
                pass
            try:
                self.railway.destroy_sandbox(job.worker_id)
            except RailwayError as exc:
                job.error = job.error or f"destroy failed: {exc}"
        job.status = status
        job.updated_at = _now()

    def poll_once(self) -> None:
        for job in list(self.jobs.values()):
            if job.status != "running" or not job.worker_id:
                continue
            try:
                self._poll_job(job)
            except RailwayError as exc:
                job.error = str(exc)
                job.updated_at = _now()

    def _poll_job(self, job: Job) -> None:
        box = self.railway.get_sandbox(job.worker_id)
        if not box or box.get("status") != "RUNNING":
            job.error = f"sandbox {box.get('status') if box else 'missing'}"
            job.worker_id = None if not box or box.get("status") == "DESTROYED" else job.worker_id
            self._finish(job, "idle_timeout")
            return
        result = self.railway.exec(job.worker_id, STATUS_SCRIPT, timeout_sec=20)
        code, tail, ip = parse_status(result.stdout)
        job.log_tail = tail
        job.egress_ip = job.egress_ip or ip
        job.updated_at = _now()
        if code is not None:
            self._finish(job, status_for_exit(code, job.spec))
            return
        if job.deadline_at and _now() >= job.deadline_at:
            job.error = "deadline exceeded"
            self._finish(job, "idle_timeout")
            return
        if time.time() - job.last_heartbeat >= self.settings.heartbeat_sec:
            self.railway.heartbeat(job.worker_id)
            job.last_heartbeat = time.time()

    def reconcile(self) -> None:
        """Adopt sandboxes that carry /job/spec.json (survives a control-plane restart)."""
        try:
            boxes = self.railway.list_sandboxes(active=True)
        except RailwayError:
            return
        known = {j.worker_id for j in self.jobs.values()}
        for box in boxes:
            if box.get("status") != "RUNNING" or box["id"] in known:
                continue
            try:
                result = self.railway.exec(box["id"], f"cat {JOB_DIR}/spec.json 2>/dev/null", timeout_sec=20)
                data = json.loads(result.stdout) if result.stdout.strip() else None
            except (RailwayError, ValueError):
                continue
            if not data or "spec" not in data:
                continue  # not ours; leave it alone
            spec = JobSpec.from_dict(data["spec"])
            created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            job = Job(
                id=data.get("job_id") or "job_" + secrets.token_hex(4),
                spec=spec,
                status="running",
                worker_id=box["id"],
                created_at=created,
                deadline_at=created + timedelta(minutes=spec.budget_minutes(created.replace(tzinfo=None)) + self.settings.grace_minutes),
                last_heartbeat=time.time(),
            )
            with self._lock:
                self.jobs[job.id] = job

    def _loop(self) -> None:
        while not self._stop.wait(self.settings.poll_sec):
            self.poll_once()
