import { AppShell } from "@/components/app-shell";
import { isUnlocked } from "@/lib/gate";
import { getRailSessionPublic } from "@/lib/rail-session";

export default async function HomePage() {
  const unlocked = await isUnlocked();
  const rail = await getRailSessionPublic();
  const initialRailSession =
    unlocked && rail.authenticated
      ? {
          carrier: rail.carrier,
          id_masked: rail.id_masked,
          verified_at: rail.verified_at,
        }
      : null;

  return (
    <AppShell
      initiallyUnlocked={unlocked}
      initialRailSession={initialRailSession}
    />
  );
}
