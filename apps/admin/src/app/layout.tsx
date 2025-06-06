import type { Metadata } from "next";
import { JetBrains_Mono, Onest } from "next/font/google";

import { Providers } from "@/lib/providers";

import "./globals.css";

const onest = Onest({ subsets: ["latin", "cyrillic"], variable: "--font-onest" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  title: { default: "Relay", template: "%s · Relay" },
  description: "Admin panel for the Relay website assistant",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${onest.variable} ${mono.variable}`} suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
