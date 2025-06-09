import { AppShell } from "@/components/shell";

// Everything behind sign-in renders on the client once the session is known, so these
// routes can't promise an instant prefetched UI.
export const instant = false;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
