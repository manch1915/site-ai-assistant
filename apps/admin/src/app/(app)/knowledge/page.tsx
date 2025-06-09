import type { Metadata } from "next";

import { KnowledgePage } from "@/views/knowledge";

// Rendered on the client after the session check, so navigation can't be instant.
export const instant = false;
export const metadata: Metadata = { title: "Knowledge" };

export default function Page() {
  return <KnowledgePage />;
}
