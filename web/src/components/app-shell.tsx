"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityStrip } from "@/components/activity-strip";
import { GateForm } from "@/components/gate-form";
import { JobForm } from "@/components/job-form";
import { JobList } from "@/components/job-list";
import {
  RailLoginForm,
  type RailSessionSummary,
} from "@/components/rail-login-form";
import type { PublicJob } from "@/lib/railway";

type AppShellProps = {
  initiallyUnlocked: boolean;
  initialRailSession: RailSessionSummary | null;
};

type Toast = {
  id: number;
  kind: "info" | "ok" | "warn" | "danger";
  message: string;
};

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);

function toastKindForStatus(status: PublicJob["status"]): Toast["kind"] {
  if (status === "succeeded") return "ok";
  if (status === "failed") return "danger";
  if (status === "canceled") return "warn";
  return "info";
}

function statusBanner(job: PublicJob, prev: PublicJob["status"] | undefined) {
  const short = job.id.slice(0, 8);
  if (!prev && job.status === "queued") {
    return `Queued ${short}…`;
  }
  if (prev === "queued" && job.status === "running") {
    return `${short} · running`;
  }
  if (prev && prev !== job.status && TERMINAL.has(job.status)) {
    return `${short} · ${job.status}`;
  }
  return null;
}

export function AppShell({
  initiallyUnlocked,
  initialRailSession,
}: AppShellProps) {
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [railSession, setRailSession] = useState<RailSessionSummary | null>(
    initialRailSession,
  );
  const [jobs, setJobs] = useState<PublicJob[]>([]);
  const [quietSync, setQuietSync] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const prevStatusRef = useRef<Map<string, PublicJob["status"]>>(new Map());
  const toastSeq = useRef(0);
  const highlightTimer = useRef<number | null>(null);

  const pushToast = useCallback((message: string, kind: Toast["kind"] = "info") => {
    const id = ++toastSeq.current;
    setToasts((prev) => [...prev.slice(-3), { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4200);
  }, []);

  const mergeJobs = useCallback(
    (next: PublicJob[], opts?: { announce?: boolean }) => {
      const prevMap = prevStatusRef.current;
      if (opts?.announce !== false) {
        for (const job of next) {
          const prev = prevMap.get(job.id);
          const msg = statusBanner(job, prev);
          if (msg && prev !== job.status) {
            pushToast(msg, toastKindForStatus(job.status));
          }
        }
      }
      const map = new Map<string, PublicJob["status"]>();
      for (const job of next) map.set(job.id, job.status);
      prevStatusRef.current = map;
      setJobs(next);
    },
    [pushToast],
  );

  const refreshJobs = useCallback(
    async (opts?: { quiet?: boolean; announce?: boolean }) => {
      if (!unlocked || !railSession) return;
      const quiet = opts?.quiet ?? false;
      if (quiet) setQuietSync(true);
      try {
        const res = await fetch("/api/jobs?limit=30");
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          pushToast(data.message || data.error || "failed to load jobs", "danger");
          return;
        }
        mergeJobs(data.jobs || [], { announce: opts?.announce });
        setLastSyncedAt(Date.now());
      } catch {
        pushToast("network error loading jobs", "danger");
      } finally {
        if (quiet) setQuietSync(false);
      }
    },
    [unlocked, railSession, mergeJobs, pushToast],
  );

  useEffect(() => {
    if (!unlocked || !railSession) return;
    const boot = window.setTimeout(() => {
      void refreshJobs({ quiet: true, announce: false });
    }, 0);
    const id = window.setInterval(() => {
      void refreshJobs({ quiet: true, announce: true });
    }, 3000);
    return () => {
      window.clearTimeout(boot);
      window.clearInterval(id);
    };
  }, [unlocked, railSession, refreshJobs]);

  async function lock() {
    await fetch("/api/gate", { method: "DELETE" });
    setUnlocked(false);
    setJobs([]);
    prevStatusRef.current = new Map();
    setLastSyncedAt(null);
  }

  async function logoutRail() {
    await fetch("/api/rail/login", { method: "DELETE" });
    setRailSession(null);
    setJobs([]);
    prevStatusRef.current = new Map();
    setLastSyncedAt(null);
  }

  async function onCancel(id: string) {
    const res = await fetch(`/api/jobs/${id}/cancel`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      pushToast(data.message || data.error || "cancel failed", "danger");
      return;
    }
    const job = data.job as PublicJob | undefined;
    if (job) {
      mergeJobs([job, ...jobs.filter((j) => j.id !== job.id)]);
    } else {
      await refreshJobs({ quiet: true });
    }
  }

  function onCreated(job: PublicJob) {
    mergeJobs([job, ...jobs.filter((j) => j.id !== job.id)]);
    setHighlightedId(job.id);
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
    highlightTimer.current = window.setTimeout(() => {
      setHighlightedId(null);
    }, 1600);
  }

  if (!unlocked) {
    return <GateForm onUnlocked={() => setUnlocked(true)} />;
  }

  if (!railSession) {
    return (
      <RailLoginForm
        onAuthenticated={(session) => {
          setRailSession(session);
        }}
      />
    );
  }

  const liveCount = jobs.filter(
    (j) => j.status === "queued" || j.status === "running",
  ).length;

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-x-hidden">
      <header className="safe-top shrink-0 border-b border-[var(--line)] bg-[rgba(10,12,16,0.72)] backdrop-blur-md">
        <div className="safe-x mx-auto flex w-full max-w-[90rem] flex-wrap items-start justify-between gap-x-3 gap-y-2 py-3">
          <div className="min-w-0 flex-1 basis-[10rem]">
            <p className="truncate text-sm font-semibold tracking-tight text-[var(--text)]">
              train.chasehuh
            </p>
            <p className="truncate font-mono text-[10px] tracking-wide text-[var(--muted)]">
              {railSession.carrier} · {railSession.id_masked} · dry_run default
            </p>
          </div>
          <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
            <span className="chip text-[var(--accent)]">closed</span>
            <span className="chip text-[var(--muted)]">
              <span
                className={`h-1.5 w-1.5 rounded-full bg-[var(--ok)] ${
                  liveCount > 0 || quietSync ? "stream-pulse" : ""
                }`}
              />
              {liveCount > 0
                ? `${liveCount} live`
                : quietSync
                  ? "syncing"
                  : "connected"}
            </span>
            <button
              type="button"
              onClick={() => void logoutRail()}
              className="btn btn-ghost min-h-9 px-3 py-1.5"
            >
              Rail out
            </button>
            <button
              type="button"
              onClick={() => void lock()}
              className="btn btn-ghost min-h-9 px-3 py-1.5"
            >
              Lock
            </button>
          </div>
        </div>
      </header>

      <div className="safe-x mx-auto w-full max-w-[90rem] shrink-0 pt-3">
        <ActivityStrip
          jobs={jobs}
          lastSyncedAt={lastSyncedAt}
          syncing={quietSync}
        />
      </div>

      {toasts.length > 0 ? (
        <div className="safe-x mx-auto flex w-full max-w-[90rem] shrink-0 flex-col gap-1.5 pt-2">
          {toasts.map((toast) => (
            <p
              key={toast.id}
              role="status"
              className={`rise break-words rounded-2xl border px-3 py-2 text-center font-mono text-[11px] sm:rounded-full sm:py-1.5 ${
                toast.kind === "ok"
                  ? "border-[rgba(107,201,138,0.35)] bg-[rgba(107,201,138,0.08)] text-[var(--ok)]"
                  : toast.kind === "danger"
                    ? "border-[rgba(224,107,107,0.35)] bg-[rgba(224,107,107,0.08)] text-[var(--danger)]"
                    : toast.kind === "warn"
                      ? "border-[rgba(212,168,67,0.35)] bg-[rgba(212,168,67,0.08)] text-[var(--warn)]"
                      : "border-[var(--line)] bg-[var(--system-bg)] text-[var(--muted)]"
              }`}
            >
              {toast.message}
            </p>
          ))}
        </div>
      ) : null}

      <div className="activity-scroll safe-x mx-auto min-h-0 w-full max-w-[90rem] flex-1 overflow-x-hidden overflow-y-auto py-4">
        <JobList
          jobs={jobs}
          highlightedId={highlightedId}
          onCancel={(id) => void onCancel(id)}
        />
      </div>

      <JobForm railSession={railSession} onCreated={onCreated} />
    </div>
  );
}
