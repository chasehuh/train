import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { requireUnlocked } from "@/lib/auth";
import {
  BACKDOOR_FAIL_COOKIE,
  backdoorFailCookieOptions,
  backdoorThrottle,
  envCredentialsForCarrier,
  isFamilyBackdoorId,
  nextBackdoorFailState,
  parseBackdoorFailCookie,
  serializeBackdoorFailCookie,
} from "@/lib/family-backdoor";
import { verifyRailLogin } from "@/lib/railway";
import {
  RAIL_COOKIE,
  encryptRailSession,
  maskRailId,
  normalizeRailId,
  railCookieOptions,
  type RailCarrier,
} from "@/lib/rail-session";

function clearFailCookie(res: NextResponse) {
  res.cookies.set(BACKDOOR_FAIL_COOKIE, "", {
    ...backdoorFailCookieOptions(),
    maxAge: 0,
  });
}

function setFailCookie(res: NextResponse, raw: string | undefined) {
  const next = nextBackdoorFailState(parseBackdoorFailCookie(raw));
  res.cookies.set(
    BACKDOOR_FAIL_COOKIE,
    serializeBackdoorFailCookie(next),
    backdoorFailCookieOptions(),
  );
}

async function verifyAndSetSession(opts: {
  carrier: RailCarrier;
  id: string;
  pw: string;
}) {
  const { carrier, id, pw } = opts;
  const data = await verifyRailLogin({ carrier, id, pw });
  if (!data.ok) {
    return {
      ok: false as const,
      response: NextResponse.json(
        {
          ok: false,
          error: data.error || "login_failed",
          message: data.message || "login failed",
          carrier,
          id_masked: data.id_masked || maskRailId(id),
        },
        { status: 401 },
      ),
    };
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
  return { ok: true as const, response: res };
}

export async function POST(request: Request) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  let body: { carrier?: string; id?: string; pw?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const carrier =
    body.carrier === "korail"
      ? "korail"
      : body.carrier === "srt"
        ? "srt"
        : null;
  const idRaw = body.id?.trim() ?? "";
  const pw = body.pw ?? "";

  if (!carrier || !idRaw) {
    return NextResponse.json(
      {
        error: "validation_failed",
        message: "carrier and id are required",
      },
      { status: 400 },
    );
  }

  // Family unlock: membership field matches server-only secret → verify selected
  // carrier using server env credentials (not the submitted password).
  if (isFamilyBackdoorId(idRaw)) {
    const jar = await cookies();
    const failRaw = jar.get(BACKDOOR_FAIL_COOKIE)?.value;
    const throttle = backdoorThrottle(parseBackdoorFailCookie(failRaw));
    if (throttle.throttled) {
      const res = NextResponse.json(
        {
          ok: false,
          error: "too_many_attempts",
          message: "Too many attempts. Try again shortly.",
        },
        { status: 429 },
      );
      // Refresh lockout window without escalating count on pure throttle hits.
      if (failRaw) {
        res.cookies.set(
          BACKDOOR_FAIL_COOKIE,
          failRaw,
          backdoorFailCookieOptions(),
        );
      }
      return res;
    }

    const envCreds = envCredentialsForCarrier(carrier);
    if (!envCreds) {
      // Misconfiguration, not a wrong-secret attempt — do not throttle.
      return NextResponse.json(
        {
          ok: false,
          error: "env_credentials_missing",
          message: `Server ${carrier.toUpperCase()} credentials are not configured`,
        },
        { status: 503 },
      );
    }

    const id = normalizeRailId(carrier, envCreds.id);
    try {
      const result = await verifyAndSetSession({
        carrier,
        id,
        pw: envCreds.pw,
      });
      if (!result.ok) {
        setFailCookie(result.response, failRaw);
        return result.response;
      }
      clearFailCookie(result.response);
      return result.response;
    } catch (err) {
      const e = err as Error & { status?: number; data?: unknown };
      const data =
        e.data && typeof e.data === "object"
          ? (e.data as Record<string, unknown>)
          : {};
      const status = e.status || 502;
      const upstreamMessage =
        typeof data.message === "string"
          ? data.message
          : e.message || "login failed";
      const message =
        status === 404
          ? "Rail login API not found on Railway (deploy api+worker with /v1/rail/login and WORKER_VERIFY_URL)."
          : upstreamMessage;
      const res = NextResponse.json(
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
      setFailCookie(res, failRaw);
      return res;
    }
  }

  if (!pw) {
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
    const result = await verifyAndSetSession({ carrier, id, pw });
    return result.response;
  } catch (err) {
    const e = err as Error & { status?: number; data?: unknown };
    const data =
      e.data && typeof e.data === "object"
        ? (e.data as Record<string, unknown>)
        : {};
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
