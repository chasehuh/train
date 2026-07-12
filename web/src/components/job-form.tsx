"use client";

import { FormEvent, useMemo, useState } from "react";
import type { RailSessionSummary } from "@/components/rail-login-form";
import { todayKstYyyymmdd } from "@/lib/date";
import type { PublicJob } from "@/lib/railway";

type JobFormProps = {
  onCreated: (job: PublicJob) => void;
  railSession: RailSessionSummary;
};

export function JobForm({ onCreated, railSession }: JobFormProps) {
  const defaultDate = useMemo(() => todayKstYyyymmdd(), []);
  const [dep, setDep] = useState(
    railSession.carrier === "srt" ? "동대구" : "대전",
  );
  const [arr, setArr] = useState(
    railSession.carrier === "srt" ? "수서" : "서울",
  );
  const [date, setDate] = useState(defaultDate);
  const [time, setTime] = useState("220800");
  const [target, setTarget] = useState(1);
  const [car, setCar] = useState("");
  const [intervalSec, setIntervalSec] = useState(3);
  const [dryRun, setDryRun] = useState(true);
  const [maxAttempts, setMaxAttempts] = useState(5);
  const [advanced, setAdvanced] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pulse, setPulse] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
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
      dep: dep.trim(),
      arr: arr.trim(),
      date: date.trim(),
      time: time.trim(),
      target,
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
      setPulse(true);
      window.setTimeout(() => setPulse(false), 550);
      onCreated(data.job as PublicJob);
    } catch {
      setError("network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="composer-sticky safe-bottom border-t border-[var(--line)] bg-[rgba(10,12,16,0.92)] pt-3 backdrop-blur-md">
      <form onSubmit={onSubmit} className="safe-x mx-auto w-full max-w-[90rem]">
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-end">
          <label className="col-span-1 min-w-0 sm:min-w-[5.5rem] sm:flex-none">
            <span className="label">carrier</span>
            <input
              className="field mt-1 font-mono"
              value={railSession.carrier === "korail" ? "korail" : "srt"}
              disabled
              readOnly
            />
          </label>
          <label className="col-span-1 min-w-0 sm:min-w-[4.5rem] sm:w-[4.5rem] sm:flex-none">
            <span className="label">seats</span>
            <input
              className="field mt-1"
              type="number"
              min={1}
              max={8}
              value={target}
              onChange={(e) => setTarget(Number(e.target.value))}
              required
            />
          </label>
          <label className="col-span-1 min-w-0 sm:min-w-[6rem] sm:flex-[1.2]">
            <span className="label">dep</span>
            <input
              className="field mt-1"
              value={dep}
              onChange={(e) => setDep(e.target.value)}
              placeholder={railSession.carrier === "srt" ? "동대구" : "대전"}
              required
            />
          </label>
          <label className="col-span-1 min-w-0 sm:min-w-[6rem] sm:flex-[1.2]">
            <span className="label">arr</span>
            <input
              className="field mt-1"
              value={arr}
              onChange={(e) => setArr(e.target.value)}
              placeholder={railSession.carrier === "srt" ? "수서" : "서울"}
              required
            />
          </label>
          <label className="col-span-1 min-w-0 sm:min-w-[7rem] sm:flex-none">
            <span className="label">date</span>
            <input
              className="field mt-1 font-mono"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              pattern="\d{8}"
              inputMode="numeric"
              placeholder={defaultDate}
              required
            />
          </label>
          <label className="col-span-1 min-w-0 sm:min-w-[6.5rem] sm:flex-none">
            <span className="label">time</span>
            <input
              className="field mt-1 font-mono"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              pattern="\d{6}"
              inputMode="numeric"
              placeholder="220800"
              required
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className={`col-span-2 min-h-11 w-full shrink-0 rounded-2xl bg-[linear-gradient(145deg,var(--accent),#c8842f)] px-4 py-2.5 text-sm font-semibold text-[#1a1208] transition enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto ${pulse ? "send-pulse" : ""}`}
          >
            {busy ? "Queueing…" : "Watch"}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 pb-1">
          <label className="flex min-h-9 items-center gap-2 font-mono text-[11px] text-[var(--muted)]">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            dry_run
          </label>
          {dryRun ? (
            <label className="flex min-h-9 items-center gap-2 font-mono text-[11px] text-[var(--muted)]">
              max
              <input
                className="field w-16 py-1"
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
            className="min-h-9 font-mono text-[10px] tracking-wide text-[var(--muted)] uppercase transition hover:text-[var(--text)]"
          >
            {advanced ? "hide options" : "more options"}
          </button>
          {error ? (
            <p
              className="w-full break-words font-mono text-[11px] text-[var(--danger)] sm:w-auto"
              role="alert"
            >
              {error}
            </p>
          ) : (
            <p className="max-w-full truncate font-mono text-[10px] text-[var(--muted)]">
              {railSession.carrier} · {railSession.id_masked} · session creds
            </p>
          )}
        </div>

        {advanced ? (
          <div className="mt-3 grid grid-cols-1 gap-2 border-t border-[var(--line)] pt-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block min-w-0">
              <span className="label">interval_sec</span>
              <input
                className="field mt-1"
                type="number"
                min={1}
                max={60}
                step={0.5}
                value={intervalSec}
                onChange={(e) => setIntervalSec(Number(e.target.value))}
                required
              />
            </label>
            {railSession.carrier === "srt" ? (
              <label className="block min-w-0">
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
      </form>
    </div>
  );
}
