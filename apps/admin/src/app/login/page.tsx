"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const done = (me: Me) => {
    queryClient.setQueryData(["me"], me);
    router.replace("/");
  };
  const login = useMutation({
    mutationFn: () => api.post<Me>("/auth/login", { email, password }),
    onSuccess: done,
  });
  const demo = useMutation({ mutationFn: () => api.post<Me>("/auth/demo"), onSuccess: done });

  return (
    <main className="grid min-h-svh lg:grid-cols-[1fr_minmax(420px,520px)]">
      <section className="relative hidden overflow-hidden bg-ink p-12 text-paper lg:flex lg:flex-col lg:justify-between dark:bg-card dark:text-ink">
        <p className="text-lg font-semibold tracking-tight">Relay</p>
        <div className="max-w-md">
          <p className="text-[34px] leading-[1.1] font-semibold tracking-[-0.02em]">
            A chat on your site that answers from your own pages and admits when it doesn&apos;t
            know.
          </p>
          <ul className="mt-8 grid gap-3 text-[15px] opacity-75">
            <li>Indexes the sitemap, PDFs, documents and your own Q&amp;A.</li>
            <li>Below the confidence threshold it hands the chat to a person in Telegram.</li>
            <li>Shows which questions your pages don&apos;t answer yet.</li>
          </ul>
        </div>
        <p className="text-[13px] opacity-50">Demo data resets every six hours.</p>
      </section>

      <section className="flex items-center justify-center px-4 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          <h1 className="text-[26px] font-semibold tracking-[-0.015em]">Sign in</h1>
          <p className="mt-1 text-ink-2">
            Look around the demo workspace of Ohm &amp; Solder, a made-up repair shop.
          </p>

          <Button
            variant="primary"
            className="mt-6 h-11 w-full"
            loading={demo.isPending}
            onClick={() => demo.mutate()}
          >
            Open the demo workspace
          </Button>

          <div className="my-7 flex items-center gap-3 text-[12.5px] text-ink-3">
            <span className="h-px flex-1 bg-line" />
            or use your account
            <span className="h-px flex-1 bg-line" />
          </div>

          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              login.mutate();
            }}
          >
            <Field label="Email" htmlFor="email">
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <ErrorNote error={login.error ?? demo.error} />
            <Button type="submit" className="h-11" loading={login.isPending}>
              Sign in
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}
