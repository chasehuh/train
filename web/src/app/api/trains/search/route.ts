import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { getRailSession } from "@/lib/rail-session";
import { searchTrains } from "@/lib/railway";
import { mockTrainResults, type TrainSearchResponse } from "@/lib/trains";

function forceMock(): boolean {
  return process.env.TRAIN_SEARCH_MOCK === "true";
}

function allowMockFallback(): boolean {
  return process.env.TRAIN_SEARCH_MOCK !== "false";
}

export async function POST(request: Request) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  try {
    const body = (await request.json()) as {
      dep?: string;
      arr?: string;
      date?: string;
      time?: string;
      available_only?: boolean;
    };

    const session = await getRailSession();
    if (!session) {
      return NextResponse.json(
        {
          ok: false,
          error: "rail_session_required",
          message: "SRT/Korail rail login required before searching",
        },
        { status: 401 },
      );
    }

    const dep = (body.dep || "").trim();
    const arr = (body.arr || "").trim();
    const date = (body.date || "").trim();
    const time = (body.time || "000000").trim() || "000000";

    if (!dep || !arr || !/^\d{8}$/.test(date) || !/^\d{6}$/.test(time)) {
      return NextResponse.json(
        {
          ok: false,
          error: "validation_failed",
          message: "dep, arr, date (YYYYMMDD), and time (HHMMSS) are required",
        },
        { status: 400 },
      );
    }

    if (forceMock()) {
      const payload: TrainSearchResponse = {
        ok: true,
        carrier: session.carrier,
        dep,
        arr,
        date,
        time,
        trains: mockTrainResults({
          carrier: session.carrier,
          dep,
          arr,
          date,
        }),
        source: "mock",
      };
      return NextResponse.json(payload);
    }

    try {
      const data = await searchTrains({
        carrier: session.carrier,
        dep,
        arr,
        date,
        time,
        available_only: body.available_only ?? false,
        credentials: { id: session.id, pw: session.pw },
      });
      return NextResponse.json({
        ...data,
        source: data.source || "live",
      });
    } catch (err) {
      const e = err as Error & { status?: number; data?: unknown };
      const status = e.status || 502;
      const upstreamUnavailable =
        status === 404 || status === 501 || status === 502 || status === 503;

      if (upstreamUnavailable && allowMockFallback()) {
        const payload: TrainSearchResponse = {
          ok: true,
          carrier: session.carrier,
          dep,
          arr,
          date,
          time,
          trains: mockTrainResults({
            carrier: session.carrier,
            dep,
            arr,
            date,
          }),
          source: "mock",
          message:
            e.message ||
            "Live search unavailable; showing mock timetable for local smoke",
        };
        return NextResponse.json(payload);
      }

      return NextResponse.json(
        {
          ok: false,
          error: e.message || "upstream_error",
          message: e.message || "search failed",
          details: e.data,
        },
        { status },
      );
    }
  } catch (err) {
    const e = err as Error;
    return NextResponse.json(
      { ok: false, error: e.message || "internal_error" },
      { status: 500 },
    );
  }
}
