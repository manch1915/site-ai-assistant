"use client";

import {
  BookOpen,
  ChartNoAxesColumn,
  LogOut,
  Menu,
  MessagesSquare,
  Moon,
  Settings2,
  Sun,
  UserRoundPlus,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { cx, Skeleton } from "@/components/ui";
import { useTheme } from "@/lib/providers";
import { SessionProvider, useSession } from "@/lib/session";

const NAV = [
  { href: "/", label: "Overview", icon: ChartNoAxesColumn },
  { href: "/inbox", label: "Conversations", icon: MessagesSquare },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/leads", label: "Leads", icon: UserRoundPlus },
  { href: "/settings", label: "Widget & settings", icon: Settings2 },
];

function SiteSwitcher() {
  const { me, site, selectSite } = useSession();
  if (me.sites.length < 2) {
    return (
      <div className="px-2">
        <p className="truncate font-semibold">{site.name}</p>
        <p className="truncate text-[12.5px] text-ink-3">{me.workspace}</p>
      </div>
    );
  }
  return (
    <label className="block px-2">
      <span className="sr-only">Site</span>
      <select
        value={site.id}
        onChange={(e) => selectSite(e.target.value)}
        className="w-full truncate rounded-lg border border-line bg-card px-2 py-1.5 font-semibold"
      >
        {me.sites.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { me, signOut } = useSession();
  const { theme, toggle } = useTheme();
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <div className="flex items-center justify-between px-2">
        <span className="text-[17px] font-semibold tracking-tight">Relay</span>
        {me.is_demo && (
          <span className="rounded-md bg-amber-soft px-2 py-0.5 text-[11.5px] font-medium text-amber">
            Demo
          </span>
        )}
      </div>
      <SiteSwitcher />
      <nav aria-label="Main" className="grid gap-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex h-9 items-center gap-3 rounded-lg px-2.5 text-[14px] transition-colors",
                active
                  ? "bg-card font-medium text-ink shadow-[0_0_0_1px_var(--line)]"
                  : "text-ink-2 hover:bg-sunken hover:text-ink",
              )}
            >
              <Icon className="size-[18px]" aria-hidden strokeWidth={1.8} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto grid gap-1 border-t border-line pt-4">
        <p className="truncate px-2.5 text-[13px] text-ink-2">{me.email}</p>
        <button
          type="button"
          onClick={toggle}
          className="flex h-9 items-center gap-3 rounded-lg px-2.5 text-ink-2 hover:bg-sunken hover:text-ink"
        >
          {theme === "dark" ? (
            <Sun className="size-[18px]" aria-hidden />
          ) : (
            <Moon className="size-[18px]" aria-hidden />
          )}
          {theme === "dark" ? "Light theme" : "Dark theme"}
        </button>
        <button
          type="button"
          onClick={() => void signOut()}
          className="flex h-9 items-center gap-3 rounded-lg px-2.5 text-ink-2 hover:bg-sunken hover:text-ink"
        >
          <LogOut className="size-[18px]" aria-hidden />
          Sign out
        </button>
      </div>
    </div>
  );
}

function LoadingShell() {
  return (
    <div className="flex min-h-svh">
      <div className="hidden w-[232px] border-r border-line p-5 lg:block">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="mt-8 h-9 w-full" />
        <Skeleton className="mt-6 h-40 w-full" />
      </div>
      <div className="flex-1 p-10">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-8 h-64 w-full" />
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <SessionProvider fallback={<LoadingShell />}>
      <div className="min-h-svh lg:grid lg:grid-cols-[232px_1fr]">
        <aside className="sticky top-0 hidden h-svh border-r border-line lg:block">
          <Sidebar />
        </aside>

        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line bg-paper/90 px-4 backdrop-blur lg:hidden">
          <span className="font-semibold">Relay</span>
          <button
            type="button"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
            className="grid size-10 place-items-center rounded-lg hover:bg-sunken"
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </header>
        {menuOpen && (
          <div className="fixed inset-0 top-14 z-10 bg-paper lg:hidden">
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </div>
        )}

        <main className="min-w-0 px-4 py-6 sm:px-8 lg:px-10 lg:py-9">
          <div className="mx-auto max-w-[1180px]">{children}</div>
        </main>
      </div>
    </SessionProvider>
  );
}
