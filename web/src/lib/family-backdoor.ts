import { timingSafeEqual } from "node:crypto";
import type { RailCarrier } from "@/lib/rail-session";

/**
 * Server-only family unlock helpers.
 * Do not import from client components — the default secret must stay off the
 * browser bundle. Prefer setting FAMILY_BACKDOOR_SECRET in production.
 */

/** Cookie tracks lightweight lockout after failed family unlock attempts. */
export const BACKDOOR_FAIL_COOKIE = "train_bd_fail";

const MAX_FAIL_DELAY_MS = 30_000;
const BASE_FAIL_DELAY_MS = 1_000;

export function familyBackdoorSecret(): string {
  return process.env.FAMILY_BACKDOOR_SECRET || "huhchaefamily";
}

/** Length-normalize then timing-safe compare (constant-time on padded buffers). */
export function timingSafeStringEqual(a: string, b: string): boolean {
  const aBuf = Buffer.from(a, "utf8");
  const bBuf = Buffer.from(b, "utf8");
  const len = Math.max(aBuf.length, bBuf.length, 1);
  const aPad = Buffer.alloc(len);
  const bPad = Buffer.alloc(len);
  aBuf.copy(aPad);
  bBuf.copy(bPad);
  const contentEqual = timingSafeEqual(aPad, bPad);
  return contentEqual && aBuf.length === bBuf.length;
}

export function isFamilyBackdoorId(idRaw: string): boolean {
  return timingSafeStringEqual(idRaw.trim(), familyBackdoorSecret());
}

export function envCredentialsForCarrier(
  carrier: RailCarrier,
): { id: string; pw: string } | null {
  if (carrier === "srt") {
    const id = process.env.SRT_ID?.trim() ?? "";
    const pw = process.env.SRT_PW ?? "";
    if (!id || !pw) return null;
    return { id, pw };
  }
  const id = process.env.KORAIL_ID?.trim() ?? "";
  const pw = process.env.KORAIL_PW ?? "";
  if (!id || !pw) return null;
  return { id, pw };
}

export type BackdoorFailState = {
  count: number;
  until: number;
};

export function parseBackdoorFailCookie(
  raw: string | undefined,
): BackdoorFailState | null {
  if (!raw) return null;
  const [countStr, untilStr] = raw.split(":");
  const count = Number(countStr);
  const until = Number(untilStr);
  if (!Number.isFinite(count) || !Number.isFinite(until) || count < 1) {
    return null;
  }
  return { count: Math.min(Math.floor(count), 20), until };
}

export function serializeBackdoorFailCookie(state: BackdoorFailState): string {
  return `${state.count}:${state.until}`;
}

export function backdoorThrottle(
  state: BackdoorFailState | null,
  now = Date.now(),
): { throttled: boolean; retryAfterMs: number } {
  if (!state || state.until <= now) {
    return { throttled: false, retryAfterMs: 0 };
  }
  return { throttled: true, retryAfterMs: state.until - now };
}

export function nextBackdoorFailState(
  prev: BackdoorFailState | null,
  now = Date.now(),
): BackdoorFailState {
  const prevCount = prev && prev.until > now - 15 * 60_000 ? prev.count : 0;
  const count = Math.min(prevCount + 1, 20);
  const delay = Math.min(
    BASE_FAIL_DELAY_MS * 2 ** Math.min(count - 1, 5),
    MAX_FAIL_DELAY_MS,
  );
  return { count, until: now + delay };
}

export function backdoorFailCookieOptions(maxAgeSeconds = 15 * 60) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}
