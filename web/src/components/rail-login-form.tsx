"use client";

import { FormEvent, useState } from "react";

export type RailSessionSummary = {
  carrier: "srt" | "korail";
  id_masked: string;
  verified_at?: string;
};

type RailLoginFormProps = {
  onAuthenticated: (session: RailSessionSummary) => void;
};

export function RailLoginForm({ onAuthenticated }: RailLoginFormProps) {
  const [carrier, setCarrier] = useState<"srt" | "korail">("srt");
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/rail/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ carrier, id, pw: password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        setError(data.message || data.error || "login failed");
        return;
      }
      onAuthenticated({
        carrier: data.carrier || carrier,
        id_masked: data.id_masked || "****",
        verified_at: data.verified_at,
      });
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
              Rail account · closed console
            </p>
          </div>
          <span className="chip shrink-0 text-[var(--accent)]">closed</span>
        </div>
      </header>

      <main className="safe-x safe-bottom rise flex flex-1 flex-col justify-center overflow-y-auto py-8">
        <div className="mx-auto w-full max-w-md space-y-6 sm:space-y-8">
          <header className="space-y-3">
            <p className="label">rail account</p>
            <h1 className="text-2xl font-medium tracking-tight text-[var(--text)] sm:text-3xl md:text-4xl">
              Sign in to SRT / KTX
            </h1>
            <p className="text-sm leading-relaxed text-[var(--muted)]">
              Site access is unlocked. Verify your rail membership so jobs run as
              your account — not a shared server env login. For SRT, use membership
              digits (hyphens OK), a phone as 010-xxxx-xxxx, or email — and the
              website password, not a card PIN.
            </p>
          </header>

          <form onSubmit={onSubmit} className="space-y-4">
            <label className="block space-y-2">
              <span className="label">carrier</span>
              <select
                className="field"
                value={carrier}
                onChange={(e) => setCarrier(e.target.value as "srt" | "korail")}
              >
                <option value="srt">SRT</option>
                <option value="korail">KTX (Korail)</option>
              </select>
            </label>

            <label className="block space-y-2">
              <span className="label">membership / phone / email</span>
              <input
                className="field"
                value={id}
                onChange={(e) => setId(e.target.value)}
                autoComplete="username"
                placeholder={carrier === "korail" ? "0752328289" : "010-1234-5678"}
                autoFocus
                required
              />
            </label>

            <label className="block space-y-2">
              <span className="label">password</span>
              <input
                className="field"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
                required
              />
            </label>

            {error ? (
              <p className="break-words text-sm text-[var(--danger)]" role="alert">
                {error}
              </p>
            ) : null}

            <button className="btn btn-primary w-full" type="submit" disabled={busy}>
              {busy ? "Verifying…" : "Verify & continue"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
