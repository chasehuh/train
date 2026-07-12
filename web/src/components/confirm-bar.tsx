"use client";

import { useState } from "react";
import type { RailSessionSummary } from "@/components/rail-login-form";
import type { PublicJob } from "@/lib/railway";
import {
  formatPrice,
  type TrainSelection,
} from "@/lib/trains";
import type { SearchQuery } from "@/components/search-bar";

type ConfirmBarProps = {
  selection: TrainSelection | null;
  query: SearchQuery;
  railSession: RailSessionSummary;
  onCreated: (job: PublicJob) => void;
  onClear: () => void;
};

export function ConfirmBar({
  selection,
  query,
  railSession,
  onCreated,
  onClear,
}: ConfirmBarProps) {
  const [dryRun, setDryRun] = useState(true);
  const [maxAttempts, setMaxAttempts] = useState(5);
  const [intervalSec, setIntervalSec] = useState(3);
  const [car, setCar] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  if (!selection) return null;

  const { train, seat } = selection;
  const offer = seat === "general" ? train.general : train.special;
  const price = formatPrice(offer.price);
  const seatLabel = offer.label;

  async function confirm() {
    setBusy(true);
    setError(null);

    const carNum = car.trim() === "" ? null : Number(car);
    if (carNum !== null && (!Number.isInteger(carNum) || carNum < 1)) {
      setError("car must be a positive integer or empty");
      setBusy(false);
      return;
    }

    const payload: Record<string, unknown> = {
      carrier: railSession.carrier,
      dep: train.dep || query.dep,
      arr: train.arr || query.arr,
      date: train.dep_date || query.date,
      time: train.dep_time,
      target: query.passengers,
      car: carNum,
      interval_sec: intervalSec,
      dry_run: dryRun,
      max_attempts: dryRun ? maxAttempts : null,
    };

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.message || data.error || `create failed (${res.status})`);
        return;
      }
      onCreated(data.job as PublicJob);
      onClear();
    } catch {
      setError("network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shrink-0 border-t border-[var(--line)] bg-[rgba(10,12,16,0.94)] backdrop-blur-md">
      <div className="mx-auto w-full max-w-[90rem] px-4 py-3 md:px-6">
        <button
          type="button"
          className="mb-2 flex w-full items-center justify-between gap-2 text-left sm:hidden"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="text-sm font-medium text-[var(--text)]">
            {train.train_type} {train.train_number} · {seatLabel}
          </span>
          <span className="font-mono text-[10px] text-[var(--muted)] uppercase">
            {open ? "hide" : "confirm"}
          </span>
        </button>

        <div className={`${open ? "block" : "hidden"} sm:block`}>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <p className="font-mono text-[10px] tracking-[0.14em] text-[var(--muted)] uppercase">
                Selected · confirm to start watch
              </p>
              <p className="mt-1 truncate text-sm font-semibold text-[var(--text)]">
                {train.train_type} {train.train_number} · {train.dep} → {train.arr}{" "}
                <span className="font-mono font-normal text-[var(--muted)]">
                  {train.dep_display} · {seatLabel}
                  {price ? ` · ${price}` : ""}
                </span>
              </p>
              <p className="mt-1 font-mono text-[10px] text-[var(--muted)]">
                job time={train.dep_time} · seats={query.passengers} ·{" "}
                {railSession.carrier} session
                {seat === "special"
                  ? " · note: worker currently reserves general path"
                  : ""}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 font-mono text-[11px] text-[var(--muted)]">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="accent-[var(--accent)]"
                />
                dry_run
              </label>
              {dryRun ? (
                <label className="flex items-center gap-2 font-mono text-[11px] text-[var(--muted)]">
                  max
                  <input
                    className="field w-14 py-1"
                    type="number"
                    min={1}
                    value={maxAttempts}
                    onChange={(e) => setMaxAttempts(Number(e.target.value))}
                  />
                </label>
              ) : null}
              <button
                type="button"
                onClick={() => setAdvanced((v) => !v)}
                className="font-mono text-[10px] tracking-wide text-[var(--muted)] uppercase transition hover:text-[var(--text)]"
              >
                {advanced ? "less" : "options"}
              </button>
              <button
                type="button"
                onClick={onClear}
                className="rounded-full border border-[var(--line)] px-3 py-2 font-mono text-[11px] text-[var(--muted)]"
              >
                Clear
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void confirm()}
                className="rounded-full bg-[linear-gradient(145deg,var(--accent),#c8842f)] px-5 py-2.5 text-sm font-semibold text-[#1a1208] transition enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Queuing…" : "Confirm"}
              </button>
            </div>
          </div>

          {advanced ? (
            <div className="mt-3 grid gap-2 border-t border-[var(--line)] pt-3 sm:grid-cols-2 lg:grid-cols-4">
              <label className="block">
                <span className="label">interval_sec</span>
                <input
                  className="field mt-1"
                  type="number"
                  min={1}
                  max={60}
                  step={0.5}
                  value={intervalSec}
                  onChange={(e) => setIntervalSec(Number(e.target.value))}
                />
              </label>
              {railSession.carrier === "srt" ? (
                <label className="block">
                  <span className="label">car · srt optional</span>
                  <input
                    className="field mt-1"
                    value={car}
                    onChange={(e) => setCar(e.target.value)}
                    placeholder="empty = any"
                    inputMode="numeric"
                  />
                </label>
              ) : null}
            </div>
          ) : null}

          {error ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
