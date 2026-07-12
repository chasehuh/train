import { AppShell } from "@/components/app-shell";
import { isUnlocked } from "@/lib/gate";

export default async function HomePage() {
  const unlocked = await isUnlocked();
  const allowEnvCreds = process.env.ALLOW_ENV_CREDS === "true";

  return (
    <AppShell initiallyUnlocked={unlocked} allowEnvCreds={allowEnvCreds} />
  );
}
