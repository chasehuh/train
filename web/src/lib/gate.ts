import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const GATE_COOKIE = "train_gate";
const GATE_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

function gateSecret(): string {
  return (
    process.env.GATE_SECRET ||
    process.env.APP_SECRET ||
    process.env.RAILWAY_API_KEY ||
    "dev-gate-secret"
  );
}

function expectedToken(): string {
  return createHmac("sha256", gateSecret())
    .update("train-gate-unlocked")
    .digest("hex");
}

export function passcodeMatches(input: string): boolean {
  const expected = process.env.GATE_PASSCODE || "chasehuh";
  const a = Buffer.from(input);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function isGateTokenValid(token: string | undefined): boolean {
  if (!token) return false;
  const expected = expectedToken();
  const a = Buffer.from(token);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export async function isUnlocked(): Promise<boolean> {
  const jar = await cookies();
  return isGateTokenValid(jar.get(GATE_COOKIE)?.value);
}

export function gateCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: GATE_TTL_SECONDS,
  };
}

export function unlockCookieValue(): string {
  return expectedToken();
}
