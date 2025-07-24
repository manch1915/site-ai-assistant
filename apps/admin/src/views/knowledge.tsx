"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Globe,
  ListTree,
  MessageCircleQuestion,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useId, useRef, useState } from "react";

import {
  Badge,
  Button,
  cx,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  PageHeader,
  Panel,
  Skeleton,
  Textarea,
} from "@/components/ui";
import { api } from "@/lib/api";
import { hostOf, timeAgo } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { FaqItem, Gap, Source, SourceKind } from "@/lib/types";

type Tab = "sources" | "faq" | "gaps";

const KIND_ICON: Record<SourceKind, typeof Globe> = {
  sitemap: ListTree,
  url: Globe,
  file: FileText,
  faq: MessageCircleQuestion,
};

const STATUS_TONE = {
  queued: "neutral",
  indexing: "amber",
  ready: "green",
  failed: "red",
} as const;

function Sources() {
  const { site, me } = useSession();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState<"url" | "sitemap">("sitemap");
  const key = ["sources", site.id];

  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => api.get<Source[]>(`/sites/${site.id}/sources`),
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.status === "queued" || s.status === "indexing")
        ? 2_000
        : false,
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: key });

  const add = useMutation({
    mutationFn: () => api.post(`/sites/${site.id}/sources`, { kind, url }),
    onSuccess: () => {
      setUrl("");
      refresh();
    },
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.post(`/sites/${site.id}/sources/upload`, form);
    },
    onSuccess: refresh,
  });
  const reindex = useMutation({
    mutationFn: (id: string) => api.post(`/sites/${site.id}/sources/${id}/reindex`),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/sites/${site.id}/sources/${id}`),
    onSuccess: refresh,
  });

  return (
    <div className="grid grid-cols-1 gap-4">
      <Panel
        title="Add knowledge"
        description="The assistant only answers from what is listed below."
      >
        <div className="grid gap-4 p-5 lg:grid-cols-[1fr_auto]">
          <form
            className="flex flex-wrap gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              add.mutate();
            }}
          >
            <select
              value={kind}
              aria-label="Source type"
              onChange={(e) => setKind(e.target.value as "url" | "sitemap")}
              className="h-10 rounded-lg border border-line bg-card px-3 text-sm"
            >
              <option value="sitemap">Whole site (sitemap)</option>
              <option value="url">Single page</option>
            </select>
            <Input
              type="url"
              required
              placeholder={
                kind === "sitemap"
                  ? "https://example.com/sitemap.xml"
                  : "https://example.com/pricing"
              }
              aria-label="Address"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="min-w-[220px] flex-1"
            />
            <Button type="submit" variant="primary" loading={add.isPending} disabled={me.is_demo}>
              Add and index
            </Button>
          </form>
          <div className="flex items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.docx,.txt,.md,.html"
              className="sr-only"
              aria-label="Upload a document"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload.mutate(file);
                e.target.value = "";
              }}
            />
            <Button onClick={() => fileInput.current?.click()} loading={upload.isPending}>
              <Upload className="size-4" aria-hidden />
              Upload PDF, DOCX or TXT
            </Button>
          </div>
          {me.is_demo && (
            <p className="text-[12.5px] text-ink-3 lg:col-span-2">
              Crawling other sites is off in the public demo. File uploads up to 2 MB work.
            </p>
          )}
          <div className="lg:col-span-2">
            <ErrorNote error={add.error ?? upload.error} />
          </div>
        </div>
      </Panel>

      <Panel title="Sources">
        <ErrorNote error={error ?? reindex.error ?? remove.error} />
        {isLoading ? (
          <div className="grid gap-2 p-5">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : !data?.length ? (
          <EmptyState title="No sources yet">
            Add your sitemap or upload a price list to start.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {data.map((source) => {
              const Icon = KIND_ICON[source.kind];
              return (
                <li
                  key={source.id}
                  className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5"
                >
                  <Icon className="size-[18px] shrink-0 text-ink-3" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{source.title}</p>
                    <p className="truncate text-[12.5px] text-ink-3">
                      {source.kind === "faq"
                        ? "Your questions and answers"
                        : source.url
                          ? hostOf(source.url)
                          : "Uploaded file"}
                      {source.indexed_at && ` · indexed ${timeAgo(source.indexed_at)}`}
                    </p>
                    {source.error && (
                      <p className="mt-1 text-[12.5px] text-danger">{source.error}</p>
                    )}
                  </div>
                  <span className="tabular text-[13px] text-ink-2">
                    {source.documents_count} {source.documents_count === 1 ? "doc" : "docs"} ·{" "}
                    {source.chunks_count} {source.chunks_count === 1 ? "chunk" : "chunks"}
                  </span>
                  <Badge tone={STATUS_TONE[source.status]}>{source.status}</Badge>
                  {source.kind !== "faq" && (
                    <span className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-label={`Reindex ${source.title}`}
                        onClick={() => reindex.mutate(source.id)}
                      >
                        <RefreshCw className="size-4" aria-hidden />
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        aria-label={`Delete ${source.title}`}
                        onClick={() => {
                          if (confirm(`Delete "${source.title}" and everything indexed from it?`))
                            remove.mutate(source.id);
                        }}
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </Button>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function FaqEditor({
  initial,
  onSave,
  onCancel,
  saving,
  submitLabel,
}: {
  initial: { question: string; answer: string };
  onSave: (value: { question: string; answer: string }) => void;
  onCancel?: () => void;
  saving: boolean;
  submitLabel: string;
}) {
  const [question, setQuestion] = useState(initial.question);
  const [answer, setAnswer] = useState(initial.answer);
  const id = useId();
  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({ question, answer });
      }}
    >
      <Field label="Question" htmlFor={`${id}-q`}>
        <Input
          id={`${id}-q`}
          required
          minLength={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
      </Field>
      <Field
        label="Answer"
        htmlFor={`${id}-a`}
        hint="Write it the way you'd say it to a customer. The assistant quotes it."
      >
        <Textarea
          id={`${id}-a`}
          required
          rows={3}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
        />
      </Field>
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" loading={saving}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

function Faq() {
  const { site } = useSession();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const key = ["faq", site.id];
  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => api.get<FaqItem[]>(`/sites/${site.id}/faq`),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ["sources", site.id] });
  };
  const create = useMutation({
    mutationFn: (value: { question: string; answer: string }) =>
      api.post(`/sites/${site.id}/faq`, value),
    onSuccess: () => {
      setAdding(false);
      refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, ...value }: { id: string; question: string; answer: string }) =>
      api.put(`/sites/${site.id}/faq/${id}`, value),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/sites/${site.id}/faq/${id}`),
    onSuccess: refresh,
  });

  return (
    <Panel
      title="Questions and answers"
      description="Short answers you write yourself. They win over page text when both match."
      actions={
        !adding && (
          <Button variant="primary" size="sm" onClick={() => setAdding(true)}>
            Add a question
          </Button>
        )
      }
    >
      <ErrorNote error={error ?? create.error ?? update.error ?? remove.error} />
      {adding && (
        <div className="border-b border-line p-5">
          <FaqEditor
            initial={{ question: "", answer: "" }}
            saving={create.isPending}
            submitLabel="Save and teach the assistant"
            onSave={(value) => create.mutate(value)}
            onCancel={() => setAdding(false)}
          />
        </div>
      )}
      {isLoading ? (
        <div className="grid gap-2 p-5">
          <Skeleton className="h-14" />
          <Skeleton className="h-14" />
        </div>
      ) : !data?.length ? (
        <EmptyState title="No questions yet">Add the ones customers ask you most often.</EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {data.map((item) => (
            <li key={item.id} className="px-5 py-4">
              {editing === item.id ? (
                <FaqEditor
                  initial={item}
                  saving={update.isPending}
                  submitLabel="Save"
                  onSave={(value) => update.mutate({ id: item.id, ...value })}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <div className="flex gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{item.question}</p>
                    <p className="mt-1 text-ink-2">{item.answer}</p>
                  </div>
                  <div className="flex shrink-0 items-start gap-1">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(item.id)}>
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      aria-label={`Delete "${item.question}"`}
                      onClick={() => {
                        if (confirm("Delete this answer?")) remove.mutate(item.id);
                      }}
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Gaps({ focus }: { focus: string | null }) {
  const { site } = useSession();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState<string | null>(focus);
  const key = ["gaps", site.id];
  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => api.get<Gap[]>(`/sites/${site.id}/gaps`),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ["faq", site.id] });
    void queryClient.invalidateQueries({ queryKey: ["analytics", site.id] });
  };
  const answer = useMutation({
    mutationFn: ({ id, ...value }: { id: string; question: string; answer: string }) =>
      api.post(`/sites/${site.id}/gaps/${id}/answer`, value),
    onSuccess: () => {
      setOpen(null);
      refresh();
    },
  });
  const dismiss = useMutation({
    mutationFn: (id: string) => api.post(`/sites/${site.id}/gaps/${id}/dismiss`),
    onSuccess: refresh,
  });

  return (
    <Panel
      title="Knowledge gaps"
      description="Questions the assistant couldn't answer from your pages, most frequent first. Similar wording is grouped."
    >
      <ErrorNote error={error ?? answer.error ?? dismiss.error} />
      {isLoading ? (
        <div className="grid gap-2 p-5">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : !data?.length ? (
        <EmptyState title="No open gaps">
          When visitors ask something your pages don&apos;t cover, it lands here.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-line">
          {data.map((gap) => (
            <li key={gap.id} className={cx("px-5 py-3.5", open === gap.id && "bg-sunken/60")}>
              <div className="flex flex-wrap items-center gap-4">
                <span
                  className="tabular grid size-8 shrink-0 place-items-center rounded-lg bg-amber-soft text-[13px] font-semibold text-amber"
                  title="Times asked"
                >
                  {gap.times_asked}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{gap.question}</p>
                  <p className="text-[12.5px] text-ink-3">
                    Last asked {timeAgo(gap.last_asked_at)}
                  </p>
                </div>
                {open !== gap.id && (
                  <span className="flex gap-1">
                    <Button size="sm" variant="primary" onClick={() => setOpen(gap.id)}>
                      Answer
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => dismiss.mutate(gap.id)}>
                      Dismiss
                    </Button>
                  </span>
                )}
              </div>
              {open === gap.id && (
                <div className="mt-4 rounded-xl border border-line bg-card p-4">
                  <FaqEditor
                    initial={{ question: gap.question, answer: "" }}
                    saving={answer.isPending}
                    submitLabel="Add to FAQ"
                    onSave={(value) => answer.mutate({ id: gap.id, ...value })}
                    onCancel={() => setOpen(null)}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function KnowledgeTabs() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = (params.get("tab") as Tab | null) ?? "sources";
  const tabs: { id: Tab; label: string }[] = [
    { id: "sources", label: "Sources" },
    { id: "faq", label: "Questions and answers" },
    { id: "gaps", label: "Knowledge gaps" },
  ];
  return (
    <>
      <div role="tablist" aria-label="Knowledge" className="mb-4 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => router.replace(`/knowledge?tab=${t.id}`, { scroll: false })}
            className={cx(
              "-mb-px h-10 border-b-2 px-3 text-sm font-medium transition-colors",
              tab === t.id
                ? "border-accent text-ink"
                : "border-transparent text-ink-2 hover:text-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "sources" && <Sources />}
        {tab === "faq" && <Faq />}
        {tab === "gaps" && <Gaps focus={params.get("gap")} />}
      </div>
    </>
  );
}

export function KnowledgePage() {
  return (
    <>
      <PageHeader
        title="Knowledge"
        description="What the assistant knows: your pages and files, the answers you wrote, and the questions nobody has answered yet."
      />
      <Suspense fallback={<Skeleton className="h-64" />}>
        <KnowledgeTabs />
      </Suspense>
    </>
  );
}
