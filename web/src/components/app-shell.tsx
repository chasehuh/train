"use client";

import { useCallback, useEffect, useState } from "react";
import { GateForm } from "@/components/gate-form";
import { JobForm } from "@/components/job-form";
import { JobList } from "@/components/job-list";
import type { PublicJob } from "@/lib/railway";

type AppShellProps = {
  initiallyUnlocked: boolean;
  allowEnvCreds: boolean;
};

export function AppShell({ initiallyUnlocked, allowEnvCreds }: AppShellProps) {
  const [unlocked, setUnlocked] = useState(initiallyUnlocked);
  const [jobs, setJobs] = useState<PublicJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [banner, setBanner] = useState<string | null>(null);

  const refreshJobs = useCallback(async () => {
    if (!unlocked) return;
    setLoading(true);
    try {
      const res = await fetch("/api/jobs?limit=30");
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setBanner(data.message || data.error || "failed to load jobs");
        return;
      }
      setJobs(data.jobs || []);
      setBanner(null);
    } catch {
      setBanner("network error loading jobs");
    } finally {
      setLoading(false);
    }
  }, [unlocked]);

  useEffect(() => {
    if (!unlocked) return;
    void refreshJobs();
    const id = window.setInterval(() => {
      void refreshJobs();
    }, 3000);
    return () => window.clearInterval(id);
  }, [unlocked, refreshJobs]);

  async function lock() {
    await fetch("/api/gate", { method: "DELETE" });
    setUnlocked(false);
    setJobs([]);
  }

  async function onCancel(id: string) {
    setBanner(null);
    const res = await fetch(`/api/jobs/${id}/cancel`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setBanner(data.message || data.error || "cancel failed");
      return;
    }
    await refreshJobs();
  }

  if (!unlocked) {
    return <GateForm onUnlocked={() => setUnlocked(true)} />;
  }

  return (
    <main className="mx-auto min-h-full w-full max-w-3xl px-6 py-12 sm:py-16">
      <header className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="label">chasehuh / train</p>
          <h1 className="text-3xl font-medium tracking-tight sm:text-4xl">
            train.chasehuh
          </h1>
          <p className="max-w-xl text-sm leading-relaxed text-[var(--muted)]">
            Queue exact-time SRT/Korail watch jobs. Dry-run stays on by default.
          </p>
        </div>
        <button className="btn btn-ghost" type="button" onClick={() => void lock()}>
          Lock
        </button>
      </header>

      {banner ? (
        <p className="mb-6 text-sm text-[var(--danger)]" role="alert">
          {banner}
        </p>
      ) : null}

      <section className="mb-12 space-y-4">
        <div>
          <p className="label">new job</p>
          <h2 className="mt-1 text-lg text-[var(--text)]">Watch / reserve</h2>
        </div>
        <JobForm
          allowEnvCreds={allowEnvCreds}
          onCreated={(job) => {
            setJobs((prev) => [job, ...prev.filter((j) => j.id !== job.id)]);
            setBanner(`Queued ${job.id.slice(0, 8)}…`);
          }}
        />
      </section>

      <JobList
        jobs={jobs}
        loading={loading}
        onCancel={(id) => void onCancel(id)}
        onRefresh={() => void refreshJobs()}
      />

      {/* TODO: Google OAuth for multi-user identity (out of scope for this PR). */}
    </main>
  );
}
