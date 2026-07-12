"use client";

import { useMemo, useState } from "react";
import { ConfirmBar } from "@/components/confirm-bar";
import { JobList } from "@/components/job-list";
import type { RailSessionSummary } from "@/components/rail-login-form";
import { SearchBar, type SearchQuery } from "@/components/search-bar";
import { TrainResults } from "@/components/train-results";
import { todayKstYyyymmdd } from "@/lib/date";
import type { PublicJob } from "@/lib/railway";
import type { TrainResult, TrainSelection } from "@/lib/trains";

type BookingDashboardProps = {
  railSession: RailSessionSummary;
  jobs: PublicJob[];
  highlightedId: string | null;
  onCancel: (id: string) => void;
  onCreated: (job: PublicJob) => void;
};

export function BookingDashboard({
  railSession,
  jobs,
  highlightedId,
  onCancel,
  onCreated,
}: BookingDashboardProps) {
  const defaults = useMemo(() => {
    const date = todayKstYyyymmdd();
    if (railSession.carrier === "srt") {
      return { dep: "수서", arr: "대전", date, time: "000000", passengers: 1 };
    }
    return { dep: "서울", arr: "동대구", date, time: "000000", passengers: 1 };
  }, [railSession.carrier]);

  const [query, setQuery] = useState<SearchQuery>(defaults);
  const [trains, setTrains] = useState<TrainResult[]>([]);
  const [source, setSource] = useState<"live" | "mock" | null>(null);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<TrainSelection | null>(null);
  const [tab, setTab] = useState<"browse" | "watches">("browse");

  async function runSearch(next: SearchQuery) {
    setBusy(true);
    setError(null);
    setSelection(null);
    try {
      const res = await fetch("/api/trains/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dep: next.dep.trim(),
          arr: next.arr.trim(),
          date: next.date.trim(),
          time: next.time.trim() || "000000",
          available_only: false,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.ok === false) {
        setTrains([]);
        setSearched(true);
        setSource(null);
        setError(data.message || data.error || `search failed (${res.status})`);
        return;
      }
      setTrains((data.trains || []) as TrainResult[]);
      setSource(data.source === "mock" ? "mock" : "live");
      setSearched(true);
      setTab("browse");
    } catch {
      setError("network error");
      setTrains([]);
      setSearched(true);
      setSource(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="mx-auto w-full max-w-[90rem] shrink-0 px-4 pt-3 md:px-6">
        <SearchBar
          carrier={railSession.carrier}
          query={query}
          busy={busy}
          onChange={setQuery}
          onSearch={(q) => void runSearch(q)}
        />
        {error ? (
          <p
            className="mt-2 font-mono text-[11px] text-[var(--danger)]"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("browse")}
            className={`rounded-full px-3 py-1.5 font-mono text-[10px] tracking-wide uppercase transition ${
              tab === "browse"
                ? "border border-[rgba(232,165,75,0.45)] bg-[rgba(232,165,75,0.12)] text-[var(--accent)]"
                : "border border-[var(--line)] text-[var(--muted)]"
            }`}
          >
            Trains
          </button>
          <button
            type="button"
            onClick={() => setTab("watches")}
            className={`rounded-full px-3 py-1.5 font-mono text-[10px] tracking-wide uppercase transition ${
              tab === "watches"
                ? "border border-[rgba(232,165,75,0.45)] bg-[rgba(232,165,75,0.12)] text-[var(--accent)]"
                : "border border-[var(--line)] text-[var(--muted)]"
            }`}
          >
            Watches ({jobs.length})
          </button>
        </div>
      </div>

      <div className="activity-scroll mx-auto min-h-0 w-full max-w-[90rem] flex-1 overflow-y-auto px-4 py-4 md:px-6">
        {tab === "browse" ? (
          <TrainResults
            trains={trains}
            source={source}
            searched={searched}
            selection={selection}
            onSelect={setSelection}
          />
        ) : (
          <JobList
            jobs={jobs}
            highlightedId={highlightedId}
            onCancel={onCancel}
          />
        )}
      </div>

      <ConfirmBar
        selection={selection}
        query={query}
        railSession={railSession}
        onCreated={(job) => {
          onCreated(job);
          setTab("watches");
        }}
        onClear={() => setSelection(null)}
      />
    </div>
  );
}
