"use client";

import { FormEvent, useState } from "react";

type GateFormProps = {
  onUnlocked: () => void;
};

export function GateForm({ onUnlocked }: GateFormProps) {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ passcode }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.message || "wrong passcode");
        return;
      }
      onUnlocked();
    } catch {
      setError("network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-x-hidden">
      <header className="safe-top shrink-0 border-b border-[var(--line)] bg-[rgba(10,12,16,0.72)] backdrop-blur-md">
        <div className="safe-x mx-auto flex w-full max-w-[90rem] items-center justify-between gap-3 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-[var(--text)]">
              train.chasehuh
            </p>
            <p className="truncate font-mono text-[10px] tracking-wide text-[var(--muted)]">
              SRT / Korail · closed console
            </p>
          </div>
          <span className="chip shrink-0 text-[var(--accent)]">closed</span>
        </div>
      </header>

      <div className="safe-x safe-bottom rise flex flex-1 flex-col items-center justify-center py-6">
        <form
          onSubmit={onSubmit}
          className="w-full max-w-md border border-[var(--line)] bg-[rgba(17,20,27,0.72)] px-4 py-5 backdrop-blur-md sm:px-5 sm:py-6"
        >
          <p className="font-mono text-[11px] tracking-[0.2em] text-[var(--accent)] uppercase">
            Closed access
          </p>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-[var(--text)] sm:text-2xl">
            Enter passcode
          </h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Unlock the reservation console. Dry-run stays on by default once
            inside.
          </p>
          <label className="mt-5 block">
            <span className="label">Passcode</span>
            <input
              autoFocus
              type="password"
              autoComplete="current-password"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              placeholder="••••••••"
              required
              className="field mt-1.5 font-mono"
            />
          </label>
          {error ? (
            <p className="mt-2 font-mono text-[11px] text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : (
            <p className="mt-2 font-mono text-[11px] text-[var(--muted)]">
              Local gate cookie · no OAuth
            </p>
          )}
          <button
            type="submit"
            disabled={busy}
            className="btn btn-primary mt-5 w-full sm:w-auto"
          >
            {busy ? "Checking…" : "Enter"}
          </button>
        </form>
      </div>
    </div>
  );
}
