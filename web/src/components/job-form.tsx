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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
      onCreated(data.job as PublicJob);
    } catch {
      setError("network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="rise space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-2">
          <span className="label">carrier</span>
          <select
            className="field"
            value={carrier}
            onChange={(e) => setCarrier(e.target.value as "srt" | "korail")}
          >
            <option value="srt">srt</option>
            <option value="korail">korail</option>
          </select>
        </label>

        <label className="block space-y-2">
          <span className="label">interval_sec</span>
          <input
            className="field"
            type="number"
            min={1}
            max={60}
            step={0.5}
            value={intervalSec}
            onChange={(e) => setIntervalSec(Number(e.target.value))}
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">dep</span>
          <input
            className="field"
            value={dep}
            onChange={(e) => setDep(e.target.value)}
            placeholder="동대구"
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">arr</span>
          <input
            className="field"
            value={arr}
            onChange={(e) => setArr(e.target.value)}
            placeholder="수서"
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">date · YYYYMMDD</span>
          <input
            className="field font-[family-name:var(--font-mono)]"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            pattern="\d{8}"
            placeholder={defaultDate}
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">time · HHMMSS</span>
          <input
            className="field font-[family-name:var(--font-mono)]"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            pattern="\d{6}"
            placeholder="220800"
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">target seats</span>
          <input
            className="field"
            type="number"
            min={1}
            max={8}
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
            required
          />
        </label>

        <label className="block space-y-2">
          <span className="label">car · srt optional</span>
          <input
            className="field"
            value={car}
            onChange={(e) => setCar(e.target.value)}
            placeholder="empty = any"
            inputMode="numeric"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-6">
        <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="accent-[var(--accent)]"
          />
          dry_run (safe default)
        </label>

        {dryRun ? (
          <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <span className="label !normal-case">max_attempts</span>
            <input
              className="field w-20 py-1"
              type="number"
              min={1}
              value={maxAttempts}
              onChange={(e) => setMaxAttempts(Number(e.target.value))}
            />
          </label>
        ) : null}
      </div>

      <div className="grid gap-4 border-t border-[var(--line)] pt-5 sm:grid-cols-2">
        <label className="block space-y-2">
          <span className="label">
            credentials id{allowEnvCreds ? " · optional" : ""}
          </span>
          <input
            className="field"
            value={credId}
            onChange={(e) => setCredId(e.target.value)}
            autoComplete="username"
            placeholder={allowEnvCreds ? "server env fallback ok" : "required"}
            required={!allowEnvCreds}
          />
        </label>
        <label className="block space-y-2">
          <span className="label">
            credentials password{allowEnvCreds ? " · optional" : ""}
          </span>
          <input
            className="field"
            type="password"
            value={credPw}
            onChange={(e) => setCredPw(e.target.value)}
            autoComplete="current-password"
            placeholder={allowEnvCreds ? "server env fallback ok" : "required"}
            required={!allowEnvCreds}
          />
        </label>
      </div>

      {error ? (
        <p className="text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}

      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? "Submitting…" : "Create job"}
      </button>
    </form>
  );
}
