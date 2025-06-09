"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  Badge,
  Button,
  cx,
  ErrorNote,
  Field,
  Input,
  PageHeader,
  Panel,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Site, TelegramStatus, WidgetSettings } from "@/lib/types";

declare global {
  interface Window {
    Relay?: {
      preview(
        element: HTMLElement,
        config: { site_name: string; settings: WidgetSettings; handoff_available: boolean },
      ): Promise<void>;
    };
  }
}

const ACCENTS = ["#0E7C66", "#2F5BD3", "#7C3AED", "#C2410C", "#B4232C", "#17181B"];

function useWidgetScript(siteKey: string): boolean {
  const [ready, setReady] = useState(() => typeof window !== "undefined" && !!window.Relay);
  useEffect(() => {
    if (ready) return;
    const script = document.createElement("script");
    script.src = "/widget.js";
    script.dataset.key = siteKey;
    script.dataset.manual = "";
    script.dataset.api = window.location.origin;
    script.onload = () => setReady(true);
    document.body.appendChild(script);
  }, [ready, siteKey]);
  return ready;
}

function Preview({
  siteName,
  settings,
  siteKey,
}: {
  siteName: string;
  settings: WidgetSettings;
  siteKey: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const ready = useWidgetScript(siteKey);
  useEffect(() => {
    if (!ready || !host.current) return;
    const element = host.current;
    const timer = setTimeout(() => {
      void window.Relay?.preview(element, {
        site_name: siteName,
        settings,
        handoff_available: settings.handoff_enabled,
      });
    }, 200);
    return () => clearTimeout(timer);
  }, [ready, siteName, settings]);
  return (
    <div className="sticky top-6">
      <p className="mb-2 text-[13px] font-medium text-ink-2">
        Live preview. It answers for real, try it.
      </p>
      <div
        className={cx(
          "h-[600px] overflow-hidden rounded-2xl border border-line",
          settings.theme === "dark"
            ? "bg-[#0f1012]"
            : "bg-[repeating-linear-gradient(135deg,var(--sunken)_0_12px,var(--paper)_12px_24px)]",
        )}
      >
        <div ref={host} className="h-full p-4" />
      </div>
    </div>
  );
}

function Snippet({ siteKey }: { siteKey: string }) {
  const [copied, setCopied] = useState(false);
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const code = `<script src="${origin}/widget.js" data-key="${siteKey}" async></script>`;
  return (
    <Panel
      title="Install on your site"
      description="Paste before </body>. The script is 1.5 KB; the chat loads when a visitor reaches for it."
    >
      <div className="flex items-start gap-2 p-5">
        <pre className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-sunken px-3 py-2.5 font-mono text-[12.5px] leading-relaxed">
          {code}
        </pre>
        <Button
          size="sm"
          aria-label="Copy snippet"
          onClick={async () => {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          }}
        >
          {copied ? (
            <Check className="size-4" aria-hidden />
          ) : (
            <Copy className="size-4" aria-hidden />
          )}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </Panel>
  );
}

function Telegram() {
  const { site } = useSession();
  const { data } = useQuery({
    queryKey: ["telegram", site.id],
    queryFn: () => api.get<TelegramStatus>(`/sites/${site.id}/telegram`),
  });
  return (
    <Panel
      title="Managers in Telegram"
      description="When a visitor asks for a person, the chat goes to your Telegram group. Reply to the bot's message and the visitor sees it."
    >
      <div className="flex flex-wrap items-center gap-3 p-5">
        {!data ? (
          <Skeleton className="h-8 w-48" />
        ) : data.connected ? (
          <Badge tone="green">Connected to {data.chat_title}</Badge>
        ) : data.connect_link ? (
          <a
            href={data.connect_link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-10 items-center gap-2 rounded-lg bg-ink px-4 text-sm font-medium text-paper dark:bg-accent dark:text-accent-ink"
          >
            <Send className="size-4" aria-hidden /> Add the bot to a Telegram group
          </a>
        ) : (
          <p className="text-[13.5px] text-ink-2">
            {data.enabled
              ? "Connecting a chat is turned off in the public demo."
              : "No Telegram bot is configured on this server. Handoffs still land in Conversations."}
          </p>
        )}
      </div>
    </Panel>
  );
}

type Draft = Pick<
  Site,
  "widget" | "instructions" | "confidence_threshold" | "monthly_token_budget"
> & {
  domains: string;
};

function toDraft(site: Site): Draft {
  return {
    widget: { ...site.widget, quick_questions: [...site.widget.quick_questions] },
    instructions: site.instructions,
    confidence_threshold: site.confidence_threshold,
    monthly_token_budget: site.monthly_token_budget,
    domains: site.allowed_domains.join("\n"),
  };
}

function SettingsForm({ site }: { site: Site }) {
  const { me } = useSession();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => toDraft(site));
  const [saved, setSaved] = useState(false);
  const widget = draft.widget;
  const setWidget = (patch: Partial<WidgetSettings>) =>
    setDraft((d) => ({ ...d, widget: { ...d.widget, ...patch } }));

  const save = useMutation({
    mutationFn: () => {
      // Send only what changed: the demo account may not touch some fields.
      const domains = draft.domains.split(/[\s,]+/).filter(Boolean);
      const body: Record<string, unknown> = {
        widget: {
          ...widget,
          quick_questions: widget.quick_questions.filter((q) => q.trim().length >= 2),
        },
        confidence_threshold: draft.confidence_threshold,
      };
      if (draft.instructions !== site.instructions) body.instructions = draft.instructions;
      if (draft.monthly_token_budget !== site.monthly_token_budget)
        body.monthly_token_budget = draft.monthly_token_budget;
      if (domains.join(",") !== site.allowed_domains.join(",")) body.allowed_domains = domains;
      return api.patch<Site>(`/sites/${site.id}`, body);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["site", site.id], updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_400px]">
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <Panel title="Look and greeting">
          <div className="grid gap-5 p-5 sm:grid-cols-2">
            <Field label="Title" htmlFor="title">
              <Input
                id="title"
                maxLength={40}
                value={widget.title}
                onChange={(e) => setWidget({ title: e.target.value })}
              />
            </Field>
            <Field label="Subtitle" htmlFor="subtitle">
              <Input
                id="subtitle"
                maxLength={60}
                value={widget.subtitle}
                onChange={(e) => setWidget({ subtitle: e.target.value })}
              />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Greeting" htmlFor="greeting">
                <Textarea
                  id="greeting"
                  rows={2}
                  maxLength={300}
                  value={widget.greeting}
                  onChange={(e) => setWidget({ greeting: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Accent colour">
              <div className="flex flex-wrap items-center gap-2">
                {ACCENTS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    aria-label={`Use ${color}`}
                    aria-pressed={widget.accent.toLowerCase() === color.toLowerCase()}
                    onClick={() => setWidget({ accent: color })}
                    className={cx(
                      "size-8 rounded-full border-2 transition-transform hover:scale-105",
                      widget.accent.toLowerCase() === color.toLowerCase()
                        ? "border-ink"
                        : "border-transparent",
                    )}
                    style={{ background: color }}
                  />
                ))}
                <input
                  type="color"
                  aria-label="Custom colour"
                  value={widget.accent}
                  onChange={(e) => setWidget({ accent: e.target.value })}
                  className="h-8 w-10 cursor-pointer rounded border border-line bg-card"
                />
              </div>
            </Field>
            <Field label={`Corner radius: ${widget.radius}px`} htmlFor="radius">
              <input
                id="radius"
                type="range"
                min={0}
                max={28}
                value={widget.radius}
                onChange={(e) => setWidget({ radius: Number(e.target.value) })}
                className="accent-[var(--accent)]"
              />
            </Field>
            <Field label="Theme" htmlFor="theme">
              <select
                id="theme"
                value={widget.theme}
                onChange={(e) => setWidget({ theme: e.target.value as WidgetSettings["theme"] })}
                className="h-10 rounded-lg border border-line bg-card px-3 text-sm"
              >
                <option value="auto">Follow the visitor&apos;s system</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </Field>
            <Field label="Position" htmlFor="position">
              <select
                id="position"
                value={widget.position}
                onChange={(e) =>
                  setWidget({ position: e.target.value as WidgetSettings["position"] })
                }
                className="h-10 rounded-lg border border-line bg-card px-3 text-sm"
              >
                <option value="right">Bottom right</option>
                <option value="left">Bottom left</option>
              </select>
            </Field>
            <Field
              label="Interface language"
              htmlFor="language"
              hint="Answers always follow the visitor's language."
            >
              <select
                id="language"
                value={widget.language}
                onChange={(e) =>
                  setWidget({ language: e.target.value as WidgetSettings["language"] })
                }
                className="h-10 rounded-lg border border-line bg-card px-3 text-sm"
              >
                <option value="auto">Same as the page</option>
                <option value="en">English</option>
                <option value="ru">Russian</option>
              </select>
            </Field>
            <fieldset className="grid gap-2 sm:col-span-2">
              <legend className="mb-1.5 text-[13px] font-medium">Suggested questions</legend>
              {[0, 1, 2, 3].map((i) => (
                <Input
                  key={i}
                  maxLength={60}
                  aria-label={`Suggested question ${i + 1}`}
                  placeholder={i === 0 ? "How much is a screen replacement?" : "Optional"}
                  value={widget.quick_questions[i] ?? ""}
                  onChange={(e) => {
                    const next = [...widget.quick_questions];
                    next[i] = e.target.value;
                    setWidget({ quick_questions: next.slice(0, 4) });
                  }}
                />
              ))}
            </fieldset>
            <div className="grid gap-2.5 sm:col-span-2">
              {(
                [
                  ["show_sources", "Show sources under answers"],
                  ["collect_leads", "Offer to leave a contact when there is no answer"],
                  ["handoff_enabled", "Offer to talk to a person"],
                ] as const
              ).map(([field, label]) => (
                <label key={field} className="flex items-center gap-2.5 text-sm">
                  <input
                    type="checkbox"
                    checked={widget[field]}
                    onChange={(e) => setWidget({ [field]: e.target.checked })}
                    className="size-4 accent-[var(--accent)]"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </Panel>

        <Panel title="How the assistant answers">
          <div className="grid gap-5 p-5">
            <Field
              label={`Confidence threshold: ${Math.round(draft.confidence_threshold * 100)}%`}
              htmlFor="threshold"
              hint="Below this the assistant says it doesn't know and offers a person or a contact form. Higher means fewer answers but fewer mistakes. 35% was tuned on the demo questions."
            >
              <input
                id="threshold"
                type="range"
                min={0.1}
                max={0.9}
                step={0.05}
                value={draft.confidence_threshold}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, confidence_threshold: Number(e.target.value) }))
                }
                className="accent-[var(--accent)]"
              />
            </Field>
            <Field
              label="Tone and extra rules"
              htmlFor="instructions"
              hint={
                me.is_demo
                  ? "Read-only in the public demo."
                  : "Added to the system prompt. Example: be brief, prices in euros."
              }
            >
              <Textarea
                id="instructions"
                rows={3}
                maxLength={2000}
                readOnly={me.is_demo}
                value={draft.instructions}
                onChange={(e) => setDraft((d) => ({ ...d, instructions: e.target.value }))}
              />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                label="Allowed domains"
                htmlFor="domains"
                hint="One per line. *.example.com covers subdomains."
              >
                <Textarea
                  id="domains"
                  rows={3}
                  readOnly={me.is_demo}
                  value={draft.domains}
                  onChange={(e) => setDraft((d) => ({ ...d, domains: e.target.value }))}
                  className="font-mono text-[13px]"
                />
              </Field>
              <Field
                label="Monthly token budget"
                htmlFor="budget"
                hint="When it runs out, answers switch to quotes from your pages."
              >
                <Input
                  id="budget"
                  type="number"
                  min={0}
                  step={10000}
                  readOnly={me.is_demo}
                  value={draft.monthly_token_budget}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, monthly_token_budget: Number(e.target.value) }))
                  }
                />
              </Field>
            </div>
          </div>
        </Panel>

        <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border border-line bg-card/95 px-4 py-3 backdrop-blur">
          <ErrorNote error={save.error} />
          {saved && (
            <span className="text-[13px] text-accent">
              Saved. The widget uses it on the next page load.
            </span>
          )}
          <Button variant="ghost" onClick={() => setDraft(toDraft(site))}>
            Reset
          </Button>
          <Button type="submit" variant="primary" loading={save.isPending}>
            Save changes
          </Button>
        </div>
      </form>

      <div className="grid content-start gap-4">
        <Preview siteName={site.name} settings={widget} siteKey={site.public_key} />
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { site } = useSession();
  const { data, error } = useQuery({
    queryKey: ["site", site.id],
    queryFn: () => api.get<Site>(`/sites/${site.id}`),
  });
  return (
    <>
      <PageHeader
        title="Widget & settings"
        description="How the chat looks on your site and how careful the assistant is."
      />
      <ErrorNote error={error} />
      {data ? (
        <div className="grid gap-6">
          <SettingsForm key={data.id} site={data} />
          <div className="grid gap-4 lg:grid-cols-2">
            <Snippet siteKey={data.public_key} />
            <Telegram />
          </div>
        </div>
      ) : (
        <Skeleton className="h-96" />
      )}
    </>
  );
}
