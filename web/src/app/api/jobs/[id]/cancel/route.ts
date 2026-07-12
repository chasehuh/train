import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { cancelJob } from "@/lib/railway";

type Params = { params: Promise<{ id: string }> };

export async function POST(_request: Request, { params }: Params) {
  const locked = await requireUnlocked();
  if (locked) return locked;

  try {
    const { id } = await params;
    const data = await cancelJob(id);
    return NextResponse.json(data);
  } catch (err) {
    const e = err as Error & { status?: number; data?: unknown };
    return NextResponse.json(
      { error: e.message || "upstream_error", details: e.data },
      { status: e.status || 502 },
    );
  }
}
