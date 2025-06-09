"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Info } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { cx, ErrorNote, PageHeader, Panel, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { compact, percent } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Overview } from "@/lib/types";

const PERIODS = [7, 30, 90] as const;

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl border border-line bg-card px-5 py-4">
      <p className="text-[13px] text-ink-2">{label}</p>
      <p className="tabular mt-1 text-[28px] leading-none font-semibold tracking-[-0.02em]">
        {value}
      </p>
      {note && <p className="mt-2 text-[12.5px] text-ink-3">{note}</p>}
    </div>
  );
}

/** Where every conversation ended up, as one bar. */
function OutcomeStrip({ data }: { data: Overview }) {
  const other = Math.max(
    data.conversations - data.resolved_confirmed - data.resolved_assumed - data.handoffs,
    0,
  );
  const parts = [
    { label: "Solved, confirmed by visitor", value: data.resolved_confirmed, color: "bg-accent" },
    { label: "Solved, no complaints", value: data.resolved_assumed, color: "bg-accent/45" },
    { label: "Handed to a person", value: data.handoffs, color: "bg-amber" },
    { label: "Left a contact or gave up", value: other, color: "bg-ink-3/35" },
  ];
  const total = Math.max(data.conversations, 1);
  return (
    <Panel
      title="Who resolved the conversation"
      description="Solved by the assistant means it answered, nobody asked for a person and the visitor didn't vote it down."
    >
      <div className="px-5 py-5">
        <div
          className="flex h-4 overflow-hidden rounded-full bg-sunken"
          role="img"
          aria-label="Outcome split"
        >
          {parts.map((part) =>
            part.value ? (
              <div
                key={part.label}
                className={part.color}
                style={{ width: `${(part.value / total) * 100}%` }}
              />
            ) : null,
          )}
        </div>
        <dl className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {parts.map((part) => (
            <div key={part.label} className="flex items-center gap-2.5 text-[13.5px]">
              <span className={cx("size-2.5 rounded-full", part.color)} aria-hidden />
              <dt className="text-ink-2">{part.label}</dt>
              <dd className="tabular ml-auto font-medium">
                {part.value}
                <span className="ml-1.5 text-ink-3">{percent(part.value / total)}</span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </Panel>
  );
}

function DailyChart({ data }: { data: Overview }) {
  const max = Math.max(...data.series.map((d) => d.conversations), 1);
  const height = 140;
  const barWidth = 100 / data.series.length;
  return (
    <Panel title="Conversations per day" description="Amber part: the visitor asked for a person.">
      <div className="px-5 pt-5 pb-4">
        <svg
          viewBox={`0 0 100 ${height}`}
          preserveAspectRatio="none"
          className="h-[150px] w-full"
          role="img"
          aria-label={`Conversations per day over the last ${data.days} days`}
        >
          {data.series.map((day, i) => {
            const total = (day.conversations / max) * (height - 4);
            const handoff = (day.handoffs / max) * (height - 4);
            const x = i * barWidth + barWidth * 0.18;
            const w = barWidth * 0.64;
            return (
              <g key={day.day}>
                <title>{`${day.day}: ${day.conversations} conversations, ${day.handoffs} handed over`}</title>
                <rect
                  x={x}
                  y={height - total}
                  width={w}
                  height={total - handoff}
                  rx={0.6}
                  className="fill-accent/75"
                />
                <rect
                  x={x}
                  y={height - handoff}
                  width={w}
                  height={handoff}
                  className="fill-amber"
                />
              </g>
            );
          })}
        </svg>
        <div className="mt-2 flex justify-between text-[12px] text-ink-3">
          <span>{data.series[0]?.day}</span>
          <span>Busiest day: {max}</span>
          <span>{data.series[data.series.length - 1]?.day}</span>
        </div>
      </div>
    </Panel>
  );
}

export function OverviewPage() {
  const { site } = useSession();
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30);
  const { data, error, isLoading } = useQuery({
    queryKey: ["analytics", site.id, days],
    queryFn: () => api.get<Overview>(`/sites/${site.id}/analytics?days=${days}`),
  });

  return (
    <>
      <PageHeader
        title="Overview"
        description={`How the assistant on ${site.name} did over the last ${days} days.`}
        actions={
          <div
            className="flex rounded-lg border border-line bg-card p-0.5"
            role="group"
            aria-label="Period"
          >
            {PERIODS.map((period) => (
              <button
                key={period}
                type="button"
                aria-pressed={days === period}
                onClick={() => setDays(period)}
                className={cx(
                  "h-8 rounded-md px-3 text-[13px] font-medium",
                  days === period
                    ? "bg-ink text-paper dark:bg-accent dark:text-accent-ink"
                    : "text-ink-2 hover:text-ink",
                )}
              >
                {period} days
              </button>
            ))}
          </div>
        }
      />
      <ErrorNote error={error} />
      {isLoading || !data ? (
        <div className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-[104px]" />
            ))}
          </div>
          <Skeleton className="h-48" />
        </div>
      ) : (
        <div className="grid gap-4">
          {!data.llm_enabled && (
            <p className="flex items-start gap-2.5 rounded-xl border border-line bg-card px-4 py-3 text-[13.5px] text-ink-2">
              <Info className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              Quote mode: no language model is connected, so the assistant answers with the most
              relevant lines from your pages and links the source. Add an API key to get written
              answers.
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Conversations" value={String(data.conversations)} />
            <Stat
              label="Solved without a person"
              value={percent(data.automation_rate)}
              note={`${data.resolved_confirmed} confirmed with a thumbs up`}
            />
            <Stat label="Handed to a person" value={String(data.handoffs)} />
            <Stat
              label="Leads"
              value={String(data.leads)}
              note={`${data.unanswered_messages} questions without an answer`}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <DailyChart data={data} />
            <OutcomeStrip data={data} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.35fr_1fr]">
            <Panel
              title="Questions your pages don't answer"
              description="Similar questions are grouped. Answer one and the assistant uses it right away."
              actions={
                <Link
                  href="/knowledge?tab=gaps"
                  className="inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline"
                >
                  All gaps <ArrowUpRight className="size-3.5" aria-hidden />
                </Link>
              }
            >
              {data.top_gaps.length ? (
                <ul className="divide-y divide-line">
                  {data.top_gaps.map((gap) => (
                    <li key={gap.id} className="flex items-center gap-4 px-5 py-3">
                      <span className="tabular grid size-8 shrink-0 place-items-center rounded-lg bg-amber-soft text-[13px] font-semibold text-amber">
                        {gap.times_asked}
                      </span>
                      <span className="min-w-0 flex-1 truncate">{gap.question}</span>
                      <Link
                        href={`/knowledge?tab=gaps&gap=${gap.id}`}
                        className="shrink-0 text-[13px] font-medium text-accent hover:underline"
                      >
                        Answer
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-8 text-center text-ink-2">
                  No open gaps. Every question got an answer.
                </p>
              )}
            </Panel>

            <Panel
              title="Model usage this month"
              description="Spending stops at the budget; answers switch to quotes."
            >
              <div className="px-5 py-5">
                <p className="tabular text-[28px] leading-none font-semibold tracking-[-0.02em]">
                  {compact(data.tokens_this_month)}
                  <span className="ml-1.5 text-[15px] font-normal text-ink-3">
                    of {compact(data.token_budget)} tokens
                  </span>
                </p>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-sunken">
                  <div
                    className={cx(
                      "h-full rounded-full",
                      data.tokens_this_month / Math.max(data.token_budget, 1) > 0.85
                        ? "bg-amber"
                        : "bg-accent",
                    )}
                    style={{
                      width: `${Math.min((data.tokens_this_month / Math.max(data.token_budget, 1)) * 100, 100)}%`,
                    }}
                  />
                </div>
              </div>
            </Panel>
          </div>
        </div>
      )}
    </>
  );
}
