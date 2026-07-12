import { NextResponse } from "next/server";
import { isUnlocked } from "@/lib/gate";

export async function requireUnlocked(): Promise<NextResponse | null> {
  if (await isUnlocked()) return null;
  return NextResponse.json(
    { error: "locked", message: "passcode required" },
    { status: 401 },
  );
}
