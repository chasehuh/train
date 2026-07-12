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
    <div className="flex h-dvh min-h-0 flex-col">
      <header className="shrink-0 border-b border-[var(--line)] bg-[rgba(10,12,16,0.72)] px-4 py-3 backdrop-blur-md md:px-6">
        <div className="mx-auto flex w-full max-w-[90rem] items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-[var(--text)]">
              train.chasehuh
            </p>
            <p className="truncate font-mono text-[10px] tracking-wide text-[var(--muted)]">
              SRT / Korail · closed console
            </p>
          </div>
          <span className="chip text-[var(--accent)]">closed</span>
        </div>
      </header>

      <div className="rise flex flex-1 flex-col items-center justify-center px-4">
        <form
          onSubmit={onSubmit}
          className="w-full max-w-md border border-[var(--line)] bg-[rgba(17,20,27,0.72)] px-5 py-6 backdrop-blur-md"
        >
          <p className="font-mono text-[11px] tracking-[0.2em] text-[var(--accent)] uppercase">
            Closed access
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--text)]">
            Enter passcode
          </h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Unlock the reservation console. Dry-run stays on by default once
            inside.
          </p>
          <label className="mt-5 block">
            <span className="font-mono text-[10px] tracking-wide text-[var(--muted)] uppercase">
              Passcode
            </span>
            <input
              autoFocus
              type="password"
              autoComplete="current-password"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              placeholder="••••••••"
              required
              className="mt-1.5 w-full border border-[var(--line)] bg-[rgba(10,12,16,0.85)] px-3 py-2.5 font-mono text-sm text-[var(--text)] outline-none placeholder:text-[var(--muted)] focus:border-[rgba(232,165,75,0.45)]"
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
            className="mt-5 rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[#14110c] transition hover:brightness-105 disabled:opacity-45"
          >
            {busy ? "Checking…" : "Enter"}
          </button>
        </form>
      </div>
    </div>
  );
}
