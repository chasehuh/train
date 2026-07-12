import { NextResponse } from "next/server";
import { requireUnlocked } from "@/lib/auth";
import { getRailSessionPublic } from "@/lib/rail-session";

export async function GET() {
  const locked = await requireUnlocked();
  if (locked) return locked;

  return NextResponse.json(await getRailSessionPublic());
}
