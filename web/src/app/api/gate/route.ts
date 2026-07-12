import { NextResponse } from "next/server";
import {
  GATE_COOKIE,
  gateCookieOptions,
  isUnlocked,
  passcodeMatches,
  unlockCookieValue,
} from "@/lib/gate";

export async function GET() {
  return NextResponse.json({ unlocked: await isUnlocked() });
}

export async function POST(request: Request) {
  let body: { passcode?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  const passcode = body.passcode ?? "";
  if (!passcodeMatches(passcode)) {
    return NextResponse.json(
      { error: "invalid_passcode", message: "wrong passcode" },
      { status: 401 },
    );
  }

  const res = NextResponse.json({ unlocked: true });
  res.cookies.set(GATE_COOKIE, unlockCookieValue(), gateCookieOptions());
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ unlocked: false });
  res.cookies.set(GATE_COOKIE, "", { ...gateCookieOptions(), maxAge: 0 });
  return res;
}
