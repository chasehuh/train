import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { verifyRailLogin } from "@/lib/railway";
import {
  RAIL_COOKIE,
  encryptRailSession,
  maskRailId,
  normalizeRailId,
  railCookieOptions,
  type RailCarrier,
} from "@/lib/rail-session";

export async function POST(request: Request) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  let body: { carrier?: string; id?: string; pw?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const carrier = body.carrier === "korail" ? "korail" : body.carrier === "srt" ? "srt" : null;
  const idRaw = body.id?.trim() ?? "";
  const pw = body.pw ?? "";

  if (!carrier || !idRaw || !pw) {
    return NextResponse.json(
      {
        error: "validation_failed",
        message: "carrier, id, and password are required",
      },
      { status: 400 },
    );
  }

  const id = normalizeRailId(carrier as RailCarrier, idRaw);

  try {
    const data = await verifyRailLogin({ carrier, id, pw });
    if (!data.ok) {
      return NextResponse.json(
        {
          ok: false,
          error: data.error || "login_failed",
          message: data.message || "login failed",
          carrier,
          id_masked: data.id_masked || maskRailId(id),
        },
        { status: 401 },
      );
    }

    const verifiedAt = data.verified_at || new Date().toISOString();
    const idNormalized = data.id_normalized || id;
    const cookie = encryptRailSession({
      carrier,
      id: idNormalized,
      pw,
      verifiedAt,
    });

    const res = NextResponse.json({
      ok: true,
      carrier,
      id_masked: data.id_masked || maskRailId(idNormalized),
      verified_at: verifiedAt,
    });
    res.cookies.set(RAIL_COOKIE, cookie, railCookieOptions());
    return res;
  } catch (err) {
    const e = err as Error & { status?: number; data?: unknown };
    const data =
      e.data && typeof e.data === "object" ? (e.data as Record<string, unknown>) : {};
    const status = e.status || 502;
    const upstreamMessage =
      typeof data.message === "string"
        ? data.message
        : e.message || "login failed";
    const message =
      status === 404
        ? "Rail login API not found on Railway (deploy api+worker with /v1/rail/login and WORKER_VERIFY_URL)."
        : upstreamMessage;
    return NextResponse.json(
      {
        ok: false,
        error:
          typeof data.error === "string"
            ? data.error
            : status === 404
              ? "rail_login_api_missing"
              : e.message || "upstream_error",
        message,
        details: e.data,
      },
      { status },
    );
  }
}

export async function DELETE() {
  const locked = await requireUnlocked();
  if (locked) return locked;

  const res = NextResponse.json({ ok: true, authenticated: false });
  res.cookies.set(RAIL_COOKIE, "", { ...railCookieOptions(), maxAge: 0 });
  return res;
}
