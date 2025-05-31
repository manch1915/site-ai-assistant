import { readSse } from "./sse";
import type { ServerMessage, Source, Status, WidgetConfig } from "./types";

export interface Session {
  id: string;
  token: string;
}

export type AnswerEvent =
  | { type: "token"; text: string }
  | {
      type: "done";
      mode: "llm" | "quote" | "no_answer" | "human";
      text?: string;
      sources?: Source[];
      actions?: ("handoff" | "lead")[];
    }
  | { type: "error"; code: string };

export type LiveEvent = { type: "message"; message: ServerMessage; status: Status };

export class ApiError extends Error {
  constructor(public readonly status: number) {
    super(`Request failed with ${status}`);
  }
}

export class WidgetApi {
  constructor(
    private readonly base: string,
    private readonly key: string,
  ) {}

  private url(path: string): string {
    return `${this.base}/v1/widget${path}`;
  }

  private async json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(this.url(path), {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
    if (!response.ok) throw new ApiError(response.status);
    return (await response.json()) as T;
  }

  private headers(session: Session): Record<string, string> {
    return { "X-Visitor-Token": session.token };
  }

  config(): Promise<WidgetConfig> {
    return this.json(`/${this.key}/config`);
  }

  start(language: string): Promise<Session> {
    return this.json<{ id: string; token: string }>(`/${this.key}/conversations`, {
      method: "POST",
      body: JSON.stringify({ page_url: location.href.slice(0, 2000), language }),
    });
  }

  transcript(session: Session): Promise<{ status: Status; messages: ServerMessage[] }> {
    return this.json(`/conversations/${session.id}/messages`, { headers: this.headers(session) });
  }

  async *ask(session: Session, text: string): AsyncGenerator<AnswerEvent> {
    const response = await fetch(this.url(`/conversations/${session.id}/messages`), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.headers(session) },
      body: JSON.stringify({ text }),
      // A lost connection should end in an error message, not an endless typing indicator.
      signal: AbortSignal.timeout(60_000),
    });
    if (!response.ok || !response.body) throw new ApiError(response.status);
    for await (const { event, data } of readSse(response.body)) {
      const payload = JSON.parse(data) as Record<string, unknown>;
      if (event === "token") yield { type: "token", text: String(payload.text ?? "") };
      else if (event === "done") yield { type: "done", ...payload } as AnswerEvent;
      else if (event === "error") yield { type: "error", code: String(payload.code) };
    }
  }

  async *live(session: Session, signal: AbortSignal): AsyncGenerator<LiveEvent> {
    const response = await fetch(this.url(`/conversations/${session.id}/events`), {
      headers: this.headers(session),
      signal,
    });
    if (!response.ok || !response.body) throw new ApiError(response.status);
    for await (const { data } of readSse(response.body)) {
      yield JSON.parse(data) as LiveEvent;
    }
  }

  handoff(session: Session): Promise<{ status: Status; messages: ServerMessage[] }> {
    return this.json(`/conversations/${session.id}/handoff`, {
      method: "POST",
      headers: this.headers(session),
    });
  }

  rate(session: Session, value: 1 | -1): Promise<unknown> {
    return this.json(`/conversations/${session.id}/rating`, {
      method: "POST",
      headers: this.headers(session),
      body: JSON.stringify({ value }),
    });
  }

  lead(
    session: Session | null,
    body: { name: string; contact: string; question: string },
  ): Promise<unknown> {
    return this.json(`/${this.key}/leads`, {
      method: "POST",
      headers: session ? this.headers(session) : {},
      body: JSON.stringify({ ...body, conversation_id: session?.id ?? null }),
    });
  }
}
