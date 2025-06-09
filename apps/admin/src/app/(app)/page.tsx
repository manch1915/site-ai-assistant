import type { Metadata } from "next";

import { OverviewPage } from "@/views/overview";

// Rendered on the client after the session check, so navigation can't be instant.
export const instant = false;
export const metadata: Metadata = { title: "Overview" };

export default function Page() {
  return <OverviewPage />;
}
