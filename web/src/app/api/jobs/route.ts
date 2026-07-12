import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { createJob, listJobs, type CreateJobBody } from "@/lib/railway";
import { getRailSession } from "@/lib/rail-session";

function allowEnvCreds(): boolean {
  return process.env.ALLOW_ENV_CREDS === "true";
}

export async function GET(request: Request) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(Number(searchParams.get("limit") || 50), 100);
    const data = await listJobs(limit);
    return NextResponse.json(data);
  } catch (err) {
    const e = err as Error & { status?: number; data?: unknown };
    return NextResponse.json(
      { error: e.message || "upstream_error", details: e.data },
      { status: e.status || 502 },
    );
  }
}

export async function POST(request: Request) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  try {
    const body = (await request.json()) as CreateJobBody;
    const session = await getRailSession();

    if (!session && !allowEnvCreds()) {
      return NextResponse.json(
        {
          error: "rail_session_required",
          message: "SRT/Korail rail login required before creating jobs",
        },
        { status: 401 },
      );
    }

    if (session && body.carrier && body.carrier !== session.carrier) {
      return NextResponse.json(
        {
          error: "carrier_mismatch",
          message: `job carrier must match rail session (${session.carrier})`,
        },
        { status: 400 },
      );
    }

    const carrier = session?.carrier ?? body.carrier;
    if (!carrier) {
      return NextResponse.json(
        { error: "validation_failed", message: "carrier is required" },
        { status: 400 },
      );
    }

    const payload: CreateJobBody = {
      carrier,
      dep: body.dep,
      arr: body.arr,
      date: body.date,
      time: body.time,
      target: body.target,
      car: body.car ?? null,
      interval_sec: body.interval_sec ?? 3,
      dry_run: body.dry_run ?? true,
      max_attempts: body.max_attempts ?? undefined,
    };

    if (session) {
      payload.credentials = { id: session.id, pw: session.pw };
    } else if (!allowEnvCreds()) {
      return NextResponse.json(
        {
          error: "credentials_required",
          message: "rail session credentials missing",
        },
        { status: 400 },
      );
    }

    const data = await createJob(payload);
    return NextResponse.json(data, { status: 201 });
  } catch (err) {
    const e = err as Error & { status?: number; data?: unknown };
    return NextResponse.json(
      { error: e.message || "upstream_error", details: e.data },
      { status: e.status || 502 },
    );
  }
}
