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
    <main className="mx-auto flex min-h-full w-full max-w-md flex-col justify-center px-6 py-16">
      <div className="rise space-y-8">
        <header className="space-y-3">
          <p className="label">closed access</p>
          <h1 className="text-3xl font-medium tracking-tight text-[var(--text)] sm:text-4xl">
            train.chasehuh
          </h1>
          <p className="text-sm leading-relaxed text-[var(--muted)]">
            Enter the passcode to open the reservation console.
          </p>
        </header>

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block space-y-2">
            <span className="label">passcode</span>
            <input
              className="field"
              type="password"
              autoComplete="current-password"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              placeholder="••••••••"
              autoFocus
              required
            />
          </label>
          {error ? (
            <p className="text-sm text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary w-full" type="submit" disabled={busy}>
            {busy ? "Checking…" : "Enter"}
          </button>
        </form>

        {/* TODO: Google OAuth for multi-user identity (out of scope for this PR). */}
      </div>
    </main>
  );
}
