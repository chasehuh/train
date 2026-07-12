/** Korail/SRT id normalization (mirrors worker.rail_verify.normalize_rail_id). */

export function normalizeRailId(carrier: "srt" | "korail", rawId: string): string {
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
