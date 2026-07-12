"use client";

import { useEffect, useState } from "react";
import type { PublicJob } from "@/lib/railway";

type JobListProps = {
  jobs: PublicJob[];
  highlightedId: string | null;
  onCancel: (id: string) => void;
};

function statusColor(status: PublicJob["status"]) {
  switch (status) {
    case "running":
      return "var(--accent-2)";
    case "succeeded":
      return "var(--ok)";
    case "failed":
      return "var(--danger)";
    case "canceled":
      return "var(--warn)";
    default:
      return "var(--muted)";
  }
}

function formatClock(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      timeZone: "Asia/Seoul",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function formatElapsed(fromIso: string | null, now: number) {
  if (!fromIso) return "—";
  const start = new Date(fromIso).getTime();
  if (Number.isNaN(start)) return "—";
  const sec = Math.max(0, Math.floor((now - start) / 1000));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return m > 0 ? `${m}m ${s.toString().padStart(2, "0")}s` : `${s}s`;
}

function lastUpdateIso(job: PublicJob) {
  return job.finished_at || job.started_at || job.created_at;
}

export function JobList({ jobs, highlightedId, onCancel }: JobListProps) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const hasLive = jobs.some(
      (j) => j.status === "queued" || j.status === "running",
    );
    if (!hasLive) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [jobs]);

  if (jobs.length === 0) {
    return (
      <div className="rise flex h-full min-h-[32vh] flex-col items-center justify-center px-2 pb-6 text-center sm:min-h-[40vh]">
        <p className="font-mono text-[11px] tracking-[0.2em] text-[var(--accent)] uppercase">
          Live activity
        </p>
        <h2 className="mt-3 text-xl font-semibold tracking-tight text-[var(--text)] sm:text-2xl">
          No watches yet
        </h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--muted)]">
          Queue an exact-time SRT or Korail watch from the composer below.
          Active jobs pulse here while the worker polls.
        </p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2 pb-6">
      {jobs.map((job) => {
        const cancelable =
          job.status === "queued" || job.status === "running";
        const active = cancelable;
        const color = statusColor(job.status);
        const elapsedFrom =
          job.status === "running"
            ? job.started_at || job.created_at
            : job.status === "queued"
              ? job.created_at
              : null;

        return (
          <li
            key={job.id}
            className={`message-in overflow-hidden rounded-2xl border border-[var(--line)] bg-[rgba(17,20,27,0.55)] px-3 py-3 sm:px-4 ${
              highlightedId === job.id ? "row-flash" : ""
            }`}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="chip"
                    style={{ color, borderColor: `${color}55` }}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${active ? "stream-pulse" : ""}`}
                      style={{ background: color }}
                    />
                    {job.status}
                  </span>
                  <span className="chip text-[var(--muted)]">
                    {job.carrier}
                  </span>
                  <span
                    className={`chip ${job.dry_run ? "text-[var(--accent)]" : "text-[var(--warn)]"}`}
                  >
                    {job.dry_run ? "dry_run" : "live"}
                  </span>
                </div>

                <p className="break-words text-sm font-medium tracking-tight text-[var(--text)]">
                  {job.dep} → {job.arr}{" "}
                  <span className="font-mono text-[12px] font-normal text-[var(--muted)]">
                    {job.travel_date} · {job.dep_time}
                  </span>
                </p>

                <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] text-[var(--muted)]">
                  <span>{job.id.slice(0, 8)}…</span>
                  <span>
                    attempts {job.attempts}
                    {job.max_attempts != null ? `/${job.max_attempts}` : ""}
                  </span>
                  <span>seats {job.target_seats}</span>
                  {job.car != null ? <span>car {job.car}</span> : null}
                  {active ? (
                    <span className="text-[var(--text)]">
                      elapsed {formatElapsed(elapsedFrom, now)}
                    </span>
                  ) : null}
                  <span>updated {formatClock(lastUpdateIso(job))}</span>
                </div>

                {job.error ? (
                  <p className="break-words font-mono text-[11px] text-[var(--danger)]">
                    {job.error}
                  </p>
                ) : null}
              </div>

              {cancelable ? (
                <button
                  type="button"
                  onClick={() => onCancel(job.id)}
                  className="min-h-10 shrink-0 rounded-full border border-[rgba(224,107,107,0.35)] px-3.5 py-2 font-mono text-[11px] tracking-wide text-[var(--danger)] uppercase transition hover:border-[var(--danger)] hover:bg-[rgba(224,107,107,0.08)]"
                >
                  Cancel
                </button>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
