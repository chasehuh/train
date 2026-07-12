import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
} from "node:crypto";
import { cookies } from "next/headers";

export const RAIL_COOKIE = "train_rail";
const RAIL_TTL_SECONDS = 60 * 60 * 12; // 12 hours

export type RailCarrier = "srt" | "korail";

export type RailSession = {
  carrier: RailCarrier;
  id: string;
  pw: string;
  verifiedAt: string;
};

export type RailSessionPublic = {
  authenticated: true;
  carrier: RailCarrier;
  id_masked: string;
  verified_at: string;
};

function railSecret(): string {
  return (
    process.env.APP_SECRET ||
    process.env.GATE_SECRET ||
    process.env.RAILWAY_API_KEY ||
    "dev-rail-secret"
  );
}

function aesKey(): Buffer {
  return createHash("sha256").update(railSecret(), "utf8").digest();
}

export function normalizeRailId(carrier: RailCarrier, rawId: string): string {
  const user = rawId.trim();
  if (!user) return user;
  const digits = [...user].filter((ch) => ch >= "0" && ch <= "9").join("");

  if (carrier === "korail") {
    if (digits.length === 11 && digits.startsWith("01")) {
      return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
    }
    if (digits) return digits;
    return user;
  }

  if (digits.length === 11 && digits.startsWith("01")) {
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  }
  if (digits && [...user].every((ch) => (ch >= "0" && ch <= "9") || ch === "-")) {
    return digits;
  }
  return user;
}

export function maskRailId(userId: string): string {
  const digits = [...userId].filter((ch) => ch >= "0" && ch <= "9").join("");
  if (digits.length >= 7) return `${digits.slice(0, 4)}****${digits.slice(-3)}`;
  if (userId.length <= 4) return "****";
  return `${userId.slice(0, 2)}****${userId.slice(-2)}`;
}

export function encryptRailSession(session: RailSession): string {
  const key = aesKey();
  const nonce = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  const plaintext = Buffer.from(JSON.stringify(session), "utf8");
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([nonce, encrypted, tag]).toString("base64url");
}

export function decryptRailSession(blob: string): RailSession | null {
  try {
    const raw = Buffer.from(blob, "base64url");
    if (raw.length < 12 + 16) return null;
    const nonce = raw.subarray(0, 12);
    const tag = raw.subarray(raw.length - 16);
    const ciphertext = raw.subarray(12, raw.length - 16);
    const decipher = createDecipheriv("aes-256-gcm", aesKey(), nonce);
    decipher.setAuthTag(tag);
    const plaintext = Buffer.concat([
      decipher.update(ciphertext),
      decipher.final(),
    ]);
    const data = JSON.parse(plaintext.toString("utf8")) as Partial<RailSession>;
    if (
      (data.carrier !== "srt" && data.carrier !== "korail") ||
      typeof data.id !== "string" ||
      typeof data.pw !== "string" ||
      typeof data.verifiedAt !== "string"
    ) {
      return null;
    }
    const ageMs = Date.now() - Date.parse(data.verifiedAt);
    if (!Number.isFinite(ageMs) || ageMs < 0 || ageMs > RAIL_TTL_SECONDS * 1000) {
      return null;
    }
    return {
      carrier: data.carrier,
      id: data.id,
      pw: data.pw,
      verifiedAt: data.verifiedAt,
    };
  } catch {
    return null;
  }
}

export function railCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge: RAIL_TTL_SECONDS,
  };
}

export async function getRailSession(): Promise<RailSession | null> {
  const jar = await cookies();
  const raw = jar.get(RAIL_COOKIE)?.value;
  if (!raw) return null;
  return decryptRailSession(raw);
}

export async function getRailSessionPublic(): Promise<
  RailSessionPublic | { authenticated: false }
> {
  const session = await getRailSession();
  if (!session) return { authenticated: false };
  return {
    authenticated: true,
    carrier: session.carrier,
    id_masked: maskRailId(session.id),
    verified_at: session.verifiedAt,
  };
}
