import type { Metadata } from "next";

import { SettingsPage } from "@/views/settings";

// Rendered on the client after the session check, so navigation can't be instant.
export const instant = false;
export const metadata: Metadata = { title: "Widget and settings" };

export default function Page() {
  return <SettingsPage />;
}
