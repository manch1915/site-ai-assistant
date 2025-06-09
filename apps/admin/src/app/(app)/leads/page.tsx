import type { Metadata } from "next";

import { LeadsPage } from "@/views/leads";

// Rendered on the client after the session check, so navigation can't be instant.
export const instant = false;
export const metadata: Metadata = { title: "Leads" };

export default function Page() {
  return <LeadsPage />;
}
