import { useCallback, useEffect, useRef, useState } from "preact/hooks";

import { ApiError, type Session, WidgetApi } from "./api";
import type { Translate } from "./i18n";
import { loadSession, saveSession } from "./storage";
import type { ChatMessage, ServerMessage, Status } from "./types";

let counter = 0;
const localKey = (): string => `local-${++counter}`;

function fromServer(message: ServerMessage): ChatMessage {
  return {
    key: `srv-${message.id}`,
    role: message.role,
    content: message.content,
    author: message.author,
    sources: message.sources,
  };
}

export interface ChatState {
  messages: ChatMessage[];
  status: Status;
  busy: boolean;
  managerName: string | null;
  send(text: string): Promise<void>;
  handoff(person: { name: string; contact: string }): Promise<boolean>;
  rate(key: string, value: 1 | -1): Promise<void>;
  submitLead(lead: { name: string; contact: string; question: string }): Promise<boolean>;
  lastQuestion: string;
}

export function useChat(
  apiBase: string,
  siteKey: string,
  language: string,
  t: Translate,
  persist: boolean,
): ChatState {
  const api = useRef(new WidgetApi(apiBase, siteKey)).current;
  const session = useRef<Session | null>(persist ? loadSession(siteKey) : null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<Status>("bot");
  const [busy, setBusy] = useState(false);
  const [managerName, setManagerName] = useState<string | null>(null);

  const patch = useCallback((key: string, change: Partial<ChatMessage>) => {
    setMessages((list) => list.map((m) => (m.key === key ? { ...m, ...change } : m)));
  }, []);

  const append = useCallback((message: ChatMessage) => {
    setMessages((list) => (list.some((m) => m.key === message.key) ? list : [...list, message]));
  }, []);

  // Restore an earlier conversation from this browser.
  useEffect(() => {
    const current = session.current;
    if (!current) return;
    api
      .transcript(current)
      .then((data) => {
        setMessages(data.messages.map(fromServer));
        setStatus(data.status);
        const manager = [...data.messages].reverse().find((m) => m.role === "manager");
        setManagerName(manager?.author ?? null);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) {
          session.current = null;
          saveSession(siteKey, null);
        }
      });
  }, [api, siteKey]);

  // While a person is involved, keep a live connection for their replies.
  useEffect(() => {
    const current = session.current;
    if (!current || (status !== "waiting" && status !== "human")) return;
    const controller = new AbortController();
    let retry = 1000;
    const connect = async (): Promise<void> => {
      while (!controller.signal.aborted) {
        try {
          for await (const event of api.live(current, controller.signal)) {
            retry = 1000;
            append(fromServer(event.message));
            setStatus(event.status);
            if (event.message.role === "manager") setManagerName(event.message.author);
          }
        } catch {
          if (controller.signal.aborted) return;
        }
        await new Promise((resolve) => setTimeout(resolve, retry));
        retry = Math.min(retry * 2, 15000);
      }
    };
    void connect();
    return () => controller.abort();
  }, [api, status, append]);

  const ensureSession = useCallback(async (): Promise<Session> => {
    if (session.current) return session.current;
    const created = await api.start(language);
    session.current = created;
    if (persist) saveSession(siteKey, created);
    return created;
  }, [api, language, persist, siteKey]);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || busy) return;
      setBusy(true);
      const answerKey = localKey();
      append({ key: localKey(), role: "visitor", content: text });
      append({ key: answerKey, role: "bot", content: "", streaming: true });
      try {
        const current = await ensureSession();
        let streamed = "";
        for await (const event of api.ask(current, text)) {
          if (event.type === "token") {
            streamed += event.text;
            patch(answerKey, { content: streamed });
          } else if (event.type === "error") {
            patch(answerKey, {
              role: "system",
              content: event.code === "rate_limited" ? t("rateLimited") : t("error"),
              streaming: false,
            });
          } else if (event.mode === "human") {
            setMessages((list) => list.filter((m) => m.key !== answerKey));
          } else {
            patch(answerKey, {
              content: event.text ?? streamed,
              sources: event.sources ?? [],
              actions: event.actions ?? [],
              streaming: false,
              rateable: event.mode === "llm" || event.mode === "quote",
            });
          }
        }
      } catch {
        patch(answerKey, { role: "system", content: t("error"), streaming: false });
      } finally {
        setBusy(false);
      }
    },
    [api, append, busy, ensureSession, patch, t],
  );

  const handoff = useCallback(
    async (person: { name: string; contact: string }) => {
      try {
        const current = await ensureSession();
        const result = await api.handoff(current, person);
        result.messages.map(fromServer).forEach(append);
        setStatus(result.status);
        return true;
      } catch {
        return false;
      }
    },
    [api, append, ensureSession],
  );

  const rate = useCallback(
    async (key: string, value: 1 | -1) => {
      patch(key, { rateable: false });
      const current = session.current;
      if (current) await api.rate(current, value).catch(() => undefined);
    },
    [api, patch],
  );

  const submitLead = useCallback(
    async (lead: { name: string; contact: string; question: string }) => {
      try {
        await api.lead(session.current, lead);
        if (session.current) {
          const data = await api.transcript(session.current);
          const last = data.messages[data.messages.length - 1];
          if (last) append(fromServer(last));
        }
        return true;
      } catch {
        return false;
      }
    },
    [api, append],
  );

  const lastQuestion = [...messages].reverse().find((m) => m.role === "visitor")?.content ?? "";

  return { messages, status, busy, managerName, send, handoff, rate, submitLead, lastQuestion };
}
