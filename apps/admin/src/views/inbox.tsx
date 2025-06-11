"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Flag, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  Badge,
  Button,
  cx,
  EmptyState,
  ErrorNote,
  Input,
  PageHeader,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, hostOf, pathOf, timeAgo } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { ConversationDetail, ConversationRow, ConversationStatus, Message } from "@/lib/types";

type Filter = "all" | "attention" | "waiting";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs attention" },
  { id: "waiting", label: "Waiting for a person" },
];

const STATUS: Record<ConversationStatus, { label: string; tone: "neutral" | "green" | "amber" }> = {
  bot: { label: "Assistant", tone: "neutral" },
  waiting: { label: "Waiting", tone: "amber" },
  human: { label: "With a person", tone: "green" },
  closed: { label: "Closed", tone: "neutral" },
};

function ConversationList({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { site } = useSession();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const params = new URLSearchParams({ limit: "50" });
  if (filter === "attention") params.set("needs_attention", "true");
  if (filter === "waiting") params.set("status", "waiting");
  if (search) params.set("q", search);

  const { data, isLoading, error } = useQuery({
    queryKey: ["conversations", site.id, filter, search],
    queryFn: () =>
      api.get<{ items: ConversationRow[]; total: number }>(
        `/sites/${site.id}/conversations?${params}`,
      ),
    refetchInterval: 10_000,
    placeholderData: keepPreviousData,
  });

  return (
    <div className="flex min-h-0 flex-col">
      <div className="grid gap-3 border-b border-line p-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3"
            aria-hidden
          />
          <Input
            type="search"
            placeholder="Search messages"
            aria-label="Search messages"
            className="pl-9"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Filter">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={cx(
                "h-7 rounded-md px-2.5 text-[12.5px] font-medium",
                filter === f.id
                  ? "bg-ink text-paper dark:bg-accent dark:text-accent-ink"
                  : "text-ink-2 hover:bg-sunken",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <ErrorNote error={error} />
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="grid gap-2 p-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : !data?.items.length ? (
          <EmptyState title="Nothing here">
            {search
              ? "No messages match this search."
              : "Conversations appear as soon as visitors write in."}
          </EmptyState>
        ) : (
          <ul>
            {data.items.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => onSelect(row.id)}
                  aria-current={selected === row.id ? "true" : undefined}
                  className={cx(
                    "grid w-full min-w-0 gap-1 overflow-hidden border-b border-line px-4 py-3 text-left transition-colors",
                    selected === row.id ? "bg-accent-soft/60" : "hover:bg-sunken",
                  )}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {row.preview || "No text"}
                    </span>
                    <span className="shrink-0 text-[12px] text-ink-3">
                      {timeAgo(row.last_message_at)}
                    </span>
                  </span>
                  <span className="flex min-w-0 flex-wrap items-center gap-1.5">
                    {row.status !== "bot" && (
                      <Badge tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Badge>
                    )}
                    {row.unanswered > 0 && <Badge tone="amber">{row.unanswered} unanswered</Badge>}
                    {row.has_lead && <Badge tone="green">Lead</Badge>}
                    {row.rating === 1 && (
                      <ThumbsUp className="size-3.5 text-accent" aria-label="Rated helpful" />
                    )}
                    {row.rating === -1 && (
                      <ThumbsDown className="size-3.5 text-danger" aria-label="Rated not helpful" />
                    )}
                    <span className="ml-auto text-[12px] text-ink-3 uppercase">{row.language}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {data && (
        <p className="border-t border-line px-4 py-2 text-[12px] text-ink-3">
          {data.total} conversations
        </p>
      )}
    </div>
  );
}

function MessageItem({ message }: { message: Message }) {
  if (message.role === "system") {
    return (
      <p className="mx-auto max-w-sm text-center text-[12.5px] text-ink-3">{message.content}</p>
    );
  }
  const visitor = message.role === "visitor";
  return (
    <div className={cx("flex flex-col gap-1.5", visitor ? "items-end" : "items-start")}>
      <span className="flex items-center gap-2 text-[12px] text-ink-3">
        {visitor
          ? "Visitor"
          : message.role === "manager"
            ? (message.author_name ?? "Manager")
            : "Assistant"}
        <span>{dateTime(message.created_at)}</span>
        {message.flagged && (
          <span className="inline-flex items-center gap-1 text-danger">
            <Flag className="size-3" aria-hidden /> possible prompt injection
          </span>
        )}
      </span>
      <div
        className={cx(
          "max-w-[min(560px,88%)] rounded-xl px-3.5 py-2.5 whitespace-pre-wrap",
          visitor && "bg-ink text-paper dark:bg-accent dark:text-accent-ink",
          message.role === "bot" && "border border-line bg-card",
          message.role === "manager" &&
            "border border-line bg-card shadow-[inset_3px_0_0_var(--accent)]",
        )}
      >
        {message.content}
      </div>
      {message.role === "bot" && (
        <div className="flex flex-wrap items-center gap-1.5">
          {message.answered === false ? (
            <Badge tone="amber">No answer in the knowledge base</Badge>
          ) : (
            message.confidence !== null && (
              <Badge tone={message.confidence >= 0.6 ? "green" : "neutral"}>
                Confidence {Math.round(message.confidence * 100)}%
              </Badge>
            )
          )}
          {message.sources.map((source, i) =>
            source.url ? (
              <a
                key={i}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="max-w-[260px] truncate rounded-md border border-line px-2 py-0.5 text-[12px] text-ink-2 hover:border-accent"
              >
                {i + 1}. {source.title}
              </a>
            ) : (
              <span
                key={i}
                className="max-w-[260px] truncate rounded-md border border-line px-2 py-0.5 text-[12px] text-ink-2"
              >
                {i + 1}. {source.title}
              </span>
            ),
          )}
        </div>
      )}
    </div>
  );
}

function ConversationView({ id, onBack }: { id: string; onBack: () => void }) {
  const { site } = useSession();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const key = ["conversation", site.id, id];

  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => api.get<ConversationDetail>(`/sites/${site.id}/conversations/${id}`),
    refetchInterval: (query) => (query.state.data?.status === "bot" ? 15_000 : 4_000),
  });

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [data?.messages.length]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ["conversations", site.id] });
  };
  const reply = useMutation({
    mutationFn: (text: string) => api.post(`/sites/${site.id}/conversations/${id}/reply`, { text }),
    onSuccess: () => {
      setDraft("");
      refresh();
    },
  });
  const close = useMutation({
    mutationFn: () => api.post(`/sites/${site.id}/conversations/${id}/close`),
    onSuccess: refresh,
  });

  if (isLoading || !data) {
    return (
      <div className="grid gap-3 p-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-20 w-3/4" />
        <Skeleton className="ml-auto h-12 w-1/2" />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
        <button
          type="button"
          onClick={onBack}
          className="grid size-8 place-items-center rounded-lg hover:bg-sunken xl:hidden"
          aria-label="Back to the list"
        >
          <ArrowLeft className="size-4" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">
            Started {dateTime(data.created_at)}
            {data.page_url && (
              <span className="text-ink-3">
                {" "}
                on {hostOf(data.page_url)}
                {pathOf(data.page_url)}
              </span>
            )}
          </p>
        </div>
        <Badge tone={STATUS[data.status].tone}>{STATUS[data.status].label}</Badge>
        {(data.status === "waiting" || data.status === "human") && (
          <Button size="sm" onClick={() => close.mutate()} loading={close.isPending}>
            Close chat
          </Button>
        )}
      </header>
      <ErrorNote error={error} />
      <div className="min-h-0 flex-1 overflow-y-auto bg-paper/60 px-5 py-5">
        <div className="mx-auto grid max-w-[760px] gap-4">
          {data.messages.map((m) => (
            <MessageItem key={m.id} message={m} />
          ))}
          <div ref={bottom} />
        </div>
      </div>
      <form
        className="grid gap-2 border-t border-line p-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (draft.trim()) reply.mutate(draft.trim());
        }}
      >
        <Textarea
          rows={2}
          value={draft}
          placeholder="Reply to the visitor. They see it in the chat right away."
          aria-label="Reply"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
              e.currentTarget.form?.requestSubmit();
          }}
        />
        <ErrorNote error={reply.error} />
        <div className="flex items-center justify-between gap-3">
          <p className="hidden text-[12px] text-ink-3 sm:block">
            Ctrl + Enter to send. Replying takes the chat over from the assistant.
          </p>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={reply.isPending}
            disabled={!draft.trim()}
          >
            Send reply
          </Button>
        </div>
      </form>
    </div>
  );
}

export function InboxPage() {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <>
      <PageHeader
        title="Conversations"
        description="Everything visitors asked, what the assistant answered and where it needed a person."
      />
      <div className="grid h-[calc(100svh-210px)] min-h-[520px] overflow-hidden rounded-xl border border-line bg-card xl:grid-cols-[340px_1fr]">
        <div
          className={cx(
            "min-h-0 border-line xl:flex xl:border-r",
            selected ? "hidden" : "flex",
            "flex-col",
          )}
        >
          <ConversationList selected={selected} onSelect={setSelected} />
        </div>
        <div className={cx("min-h-0 flex-col", selected ? "flex" : "hidden xl:flex")}>
          {selected ? (
            <ConversationView key={selected} id={selected} onBack={() => setSelected(null)} />
          ) : (
            <EmptyState title="Pick a conversation">
              The full transcript, sources and confidence show up here.
            </EmptyState>
          )}
        </div>
      </div>
    </>
  );
}
