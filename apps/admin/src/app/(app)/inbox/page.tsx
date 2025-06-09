import type { Metadata } from "next";

import { InboxPage } from "@/views/inbox";

// Rendered on the client after the session check, so navigation can't be instant.
export const instant = false;
export const metadata: Metadata = { title: "Conversations" };

export default function Page() {
  return <InboxPage />;
}
