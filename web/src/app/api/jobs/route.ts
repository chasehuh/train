import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { createJob, listJobs, type CreateJobBody } from "@/lib/railway";

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
    const body = (await request.json()) as CreateJobBody & {
      credentials?: { id?: string; pw?: string };
    };

    const id = body.credentials?.id?.trim() ?? "";
    const pw = body.credentials?.pw?.trim() ?? "";

    if ((!id || !pw) && !allowEnvCreds()) {
      return NextResponse.json(
        {
          error: "credentials_required",
          message:
            "SRT/Korail id and password are required (or set ALLOW_ENV_CREDS=true for env fallback)",
        },
        { status: 400 },
      );
    }

    const payload: CreateJobBody = {
      carrier: body.carrier,
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

    if (id && pw) {
      payload.credentials = { id, pw };
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
