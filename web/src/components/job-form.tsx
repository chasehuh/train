"use client";

import { FormEvent, useMemo, useState } from "react";
import { todayKstYyyymmdd } from "@/lib/date";
import type { PublicJob } from "@/lib/railway";

type JobFormProps = {
  onCreated: (job: PublicJob) => void;
  allowEnvCreds: boolean;
};

export function JobForm({ onCreated, allowEnvCreds }: JobFormProps) {
  const defaultDate = useMemo(() => todayKstYyyymmdd(), []);
  const [carrier, setCarrier] = useState<"srt" | "korail">("srt");
  const [dep, setDep] = useState("동대구");
  const [arr, setArr] = useState("수서");
  const [date, setDate] = useState(defaultDate);
  const [time, setTime] = useState("220800");
  const [target, setTarget] = useState(1);
  const [car, setCar] = useState("");
  const [intervalSec, setIntervalSec] = useState(3);
  const [dryRun, setDryRun] = useState(true);
  const [maxAttempts, setMaxAttempts] = useState(5);
  const [credId, setCredId] = useState("");
  const [credPw, setCredPw] = useState("");
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
      carrier,
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

    if (credId.trim() && credPw.trim()) {
      payload.credentials = { id: credId.trim(), pw: credPw.trim() };
    }

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
    <div className="border-t border-[var(--line)] bg-[rgba(10,12,16,0.88)] px-4 py-3 backdrop-blur-md md:px-6">
      <form onSubmit={onSubmit} className="mx-auto w-full max-w-[90rem]">
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-[5.5rem] flex-1 sm:flex-none">
            <span className="label">carrier</span>
            <select
              className="field mt-1 font-mono"
              value={carrier}
              onChange={(e) => setCarrier(e.target.value as "srt" | "korail")}
            >
              <option value="srt">srt</option>
              <option value="korail">korail</option>
            </select>
          </label>
          <label className="min-w-[6rem] flex-[1.2]">
            <span className="label">dep</span>
            <input
              className="field mt-1"
              value={dep}
              onChange={(e) => setDep(e.target.value)}
              placeholder="동대구"
              required
            />
          </label>
          <label className="min-w-[6rem] flex-[1.2]">
            <span className="label">arr</span>
            <input
              className="field mt-1"
              value={arr}
              onChange={(e) => setArr(e.target.value)}
              placeholder="수서"
              required
            />
          </label>
          <label className="min-w-[7rem] flex-1 sm:flex-none">
            <span className="label">date</span>
            <input
              className="field mt-1 font-mono"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              pattern="\d{8}"
              placeholder={defaultDate}
              required
            />
          </label>
          <label className="min-w-[6.5rem] flex-1 sm:flex-none">
            <span className="label">time</span>
            <input
              className="field mt-1 font-mono"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              pattern="\d{6}"
              placeholder="220800"
              required
            />
          </label>
          <label className="w-[4.5rem]">
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
          <button
            type="submit"
            disabled={busy}
            className={`shrink-0 rounded-2xl bg-[linear-gradient(145deg,var(--accent),#c8842f)] px-4 py-2.5 text-sm font-semibold text-[#1a1208] transition enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40 ${pulse ? "send-pulse" : ""}`}
          >
            {busy ? "Queueing…" : "Watch"}
          </button>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
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
            {advanced ? "hide options" : "more options"}
          </button>
          {error ? (
            <p className="font-mono text-[11px] text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : (
            <p className="font-mono text-[10px] text-[var(--muted)]">
              exact-time watch · dry_run default on
            </p>
          )}
        </div>

        {advanced || !allowEnvCreds ? (
          <div className="mt-3 grid gap-2 border-t border-[var(--line)] pt-3 sm:grid-cols-2 lg:grid-cols-4">
            {advanced ? (
              <>
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
                    required
                  />
                </label>
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
              </>
            ) : null}
            <label className="block">
              <span className="label">
                credentials id{allowEnvCreds ? " · optional" : ""}
              </span>
              <input
                className="field mt-1"
                value={credId}
                onChange={(e) => setCredId(e.target.value)}
                autoComplete="username"
                placeholder={allowEnvCreds ? "env fallback ok" : "required"}
                required={!allowEnvCreds}
              />
            </label>
            <label className="block">
              <span className="label">
                credentials password{allowEnvCreds ? " · optional" : ""}
              </span>
              <input
                className="field mt-1"
                type="password"
                value={credPw}
                onChange={(e) => setCredPw(e.target.value)}
                autoComplete="current-password"
                placeholder={allowEnvCreds ? "env fallback ok" : "required"}
                required={!allowEnvCreds}
              />
            </label>
          </div>
        ) : null}
      </form>
    </div>
  );
}
