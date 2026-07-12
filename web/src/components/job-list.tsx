"use client";

import type { PublicJob } from "@/lib/railway";

type JobListProps = {
  jobs: PublicJob[];
  loading?: boolean;
  onCancel: (id: string) => void;
  onRefresh: () => void;
};

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-CA", {
      timeZone: "Asia/Seoul",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

export function JobList({ jobs, loading, onCancel, onRefresh }: JobListProps) {
  return (
    <section className="rise space-y-4" style={{ animationDelay: "60ms" }}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="label">recent jobs</p>
          <h2 className="mt-1 text-lg text-[var(--text)]">Status</h2>
        </div>
        <button className="btn btn-ghost" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? "Polling…" : "Refresh"}
        </button>
      </div>

      {jobs.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No jobs yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
          {jobs.map((job) => {
            const cancelable =
              job.status === "queued" || job.status === "running";
            return (
              <li
                key={job.id}
                className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span
                      className={`font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.08em] status-${job.status}`}
                    >
                      {job.status}
                    </span>
                    <span className="font-[family-name:var(--font-mono)] text-xs text-[var(--muted)]">
                      {job.carrier} · {job.dry_run ? "dry_run" : "live"}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--text)]">
                    {job.dep} → {job.arr}{" "}
                    <span className="text-[var(--muted)]">
                      {job.travel_date} {job.dep_time}
                    </span>
                  </p>
                  <p className="font-[family-name:var(--font-mono)] text-[0.7rem] text-[var(--muted)]">
                    {job.id.slice(0, 8)}… · seats {job.target_seats}
                    {job.car != null ? ` · car ${job.car}` : ""} · attempts{" "}
                    {job.attempts}
                    {job.max_attempts != null ? `/${job.max_attempts}` : ""}
                  </p>
                  <p className="text-xs text-[var(--muted)]">
                    created {formatWhen(job.created_at)}
                    {job.error ? (
                      <span className="text-[var(--danger)]"> · {job.error}</span>
                    ) : null}
                  </p>
                </div>
                {cancelable ? (
                  <button
                    className="btn btn-danger shrink-0 self-start"
                    type="button"
                    onClick={() => onCancel(job.id)}
                  >
                    Cancel
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
