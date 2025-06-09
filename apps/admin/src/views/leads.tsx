"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ErrorNote, PageHeader, Panel, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Lead, LeadStatus } from "@/lib/types";

const STATUSES: { value: LeadStatus; label: string }[] = [
  { value: "new", label: "New" },
  { value: "in_progress", label: "In progress" },
  { value: "done", label: "Done" },
];

export function LeadsPage() {
  const { site } = useSession();
  const queryClient = useQueryClient();
  const key = ["leads", site.id];
  const { data, isLoading, error } = useQuery({
    queryKey: key,
    queryFn: () => api.get<Lead[]>(`/sites/${site.id}/leads`),
  });
  const update = useMutation({
    mutationFn: ({ id, status }: { id: string; status: LeadStatus }) =>
      api.patch(`/sites/${site.id}/leads/${id}`, { status }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <>
      <PageHeader
        title="Leads"
        description="Contacts visitors left in the chat. Each one also goes to your Telegram chat if it's connected."
      />
      <Panel>
        <ErrorNote error={error ?? update.error} />
        {isLoading ? (
          <div className="grid gap-2 p-5">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : !data?.length ? (
          <EmptyState title="No leads yet">
            When the assistant can&apos;t answer, it offers the visitor to leave a contact.
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="border-b border-line text-[12.5px] text-ink-2">
                  <th scope="col" className="px-5 py-3 font-medium">
                    Name
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Contact
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Request
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Received
                  </th>
                  <th scope="col" className="px-5 py-3 font-medium">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.map((lead) => (
                  <tr key={lead.id} className="align-top transition-colors hover:bg-sunken/60">
                    <td className="px-5 py-3.5 font-medium">{lead.name}</td>
                    <td className="px-5 py-3.5 font-mono text-[13px]">{lead.contact}</td>
                    <td className="max-w-[340px] px-5 py-3.5 text-ink-2">
                      {lead.question || "No details"}
                    </td>
                    <td className="tabular px-5 py-3.5 whitespace-nowrap text-ink-2">
                      {dateTime(lead.created_at)}
                    </td>
                    <td className="px-5 py-3">
                      <select
                        aria-label={`Status of ${lead.name}`}
                        value={lead.status}
                        onChange={(e) =>
                          update.mutate({ id: lead.id, status: e.target.value as LeadStatus })
                        }
                        className="h-8 rounded-lg border border-line bg-card px-2 text-[13px]"
                      >
                        {STATUSES.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
