"use client";

import type { PublicJob } from "@/lib/railway";

type ActivityStripProps = {
  jobs: PublicJob[];
  lastSyncedAt: number | null;
  syncing: boolean;
};

export function ActivityStrip({
  jobs,
  lastSyncedAt,
  syncing,
}: ActivityStripProps) {
  const queued = jobs.filter((j) => j.status === "queued").length;
  const running = jobs.filter((j) => j.status === "running").length;
  const live = queued + running;
  const syncedLabel =
    lastSyncedAt == null
      ? "syncing…"
      : `synced ${new Date(lastSyncedAt).toLocaleTimeString("en-GB", {
          hour12: false,
        })}`;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--system-bg)]">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex min-w-0 flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-medium tracking-[0.14em] text-[var(--muted)] uppercase">
            Activity
          </span>
          <span className="chip text-[var(--muted)]">
            <span
              className={`h-1.5 w-1.5 rounded-full bg-[var(--accent)] ${live > 0 || syncing ? "stream-pulse" : ""}`}
            />
            {live > 0 ? `${live} live` : "idle"}
          </span>
          <span className="chip status-queued">{queued} queued</span>
          <span className="chip status-running">{running} running</span>
        </div>
        <span className="shrink-0 font-mono text-[10px] text-[var(--muted)]">
          {syncing ? "refresh…" : syncedLabel}
        </span>
      </div>
    </div>
  );
}
