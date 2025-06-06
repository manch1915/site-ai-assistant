"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, type ReactNode } from "react";

import { api, ApiError } from "./api";
import { useStored, writeStored } from "./local-store";
import type { Me, SiteBrief } from "./types";

interface SessionValue {
  me: Me;
  site: SiteBrief;
  selectSite: (id: string) => void;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside of SessionProvider");
  return value;
}

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api.get<Me>("/me"), staleTime: 60_000 });
}

export function SessionProvider({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback: ReactNode;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const me = useMe();
  const siteId = useStored("relay-site", () => "");

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) router.replace("/login");
  }, [me.error, router]);

  if (!me.data) return <>{fallback}</>;
  const site = me.data.sites.find((s) => s.id === siteId) ?? me.data.sites[0];
  if (!site) return <>{fallback}</>;

  const value: SessionValue = {
    me: me.data,
    site,
    selectSite: (id) => writeStored("relay-site", id),
    signOut: async () => {
      await api.post("/auth/logout").catch(() => undefined);
      queryClient.clear();
      router.replace("/login");
    },
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
