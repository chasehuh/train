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
    <main className="mx-auto flex min-h-full w-full max-w-md flex-col justify-center px-6 py-16">
      <div className="rise space-y-8">
        <header className="space-y-3">
          <p className="label">rail account</p>
          <h1 className="text-3xl font-medium tracking-tight text-[var(--text)] sm:text-4xl">
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
            <p className="text-sm text-[var(--danger)]" role="alert">
              {error}
            </p>
          ) : null}

          <button className="btn btn-primary w-full" type="submit" disabled={busy}>
            {busy ? "Verifying…" : "Verify & continue"}
          </button>
        </form>
      </div>
    </main>
  );
}
