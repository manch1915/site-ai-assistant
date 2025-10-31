import { render } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";

import { readableOn } from "./color";
import { isValidContact } from "./contact";
import { type Lang, pickLanguage, type Translate, translator } from "./i18n";
import { Icon } from "./icons";
import { Markdown } from "./markdown";
import { setOpenFlag } from "./storage";
import styles from "./styles.css?inline";
import type {
  ChatMessage,
  LocalizedTexts,
  MountOptions,
  Source,
  WidgetConfig,
  WidgetSettings,
} from "./types";
import { type ChatState, useChat } from "./use-chat";

interface Controls {
  open(): void;
  close(): void;
}

/** Owner-written Russian texts when the interface is Russian; empty ones fall back. */
export function localizedTexts(settings: WidgetSettings, lang: Lang): LocalizedTexts {
  const ru = lang === "ru" ? settings.ru : undefined;
  return {
    title: ru?.title || settings.title,
    subtitle: ru?.subtitle || settings.subtitle,
    greeting: ru?.greeting || settings.greeting,
    quick_questions: ru?.quick_questions?.length ? ru.quick_questions : settings.quick_questions,
  };
}

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter((w) => /\w/.test(w))
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase())
      .join("") || "?"
  );
}

function hostOf(url: string | null): string {
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function Sources(props: { sources: Source[]; t: Translate; idPrefix: string }) {
  const { sources, t, idPrefix } = props;
  return (
    <div class="sources" aria-label={t("sources")}>
      {sources.map((source, i) => {
        const label = (
          <>
            <span class="num">{i + 1}</span>
            <span class="title">{source.title}</span>
            {source.url ? (
              <span class="host">{hostOf(source.url)}</span>
            ) : (
              <Icon name="doc" size={14} />
            )}
          </>
        );
        return source.url ? (
          <a
            class="source"
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            id={`${idPrefix}-${i + 1}`}
          >
            {label}
          </a>
        ) : (
          <span class="source" id={`${idPrefix}-${i + 1}`} tabIndex={-1}>
            {label}
          </span>
        );
      })}
    </div>
  );
}

type ContactKind = "lead" | "handoff";

function ContactForm(props: {
  kind: ContactKind;
  t: Translate;
  question: string;
  chat: ChatState;
  onDone: () => void;
}) {
  const { kind, t, question, chat, onDone } = props;
  const [state, setState] = useState<"idle" | "sending" | "error">("idle");
  const [contactError, setContactError] = useState(false);
  const contactRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const handoff = kind === "handoff";

  useEffect(() => {
    // The error line pushes the buttons below the fold of the message list.
    const list = formRef.current?.parentElement;
    if (contactError && list) list.scrollTop = list.scrollHeight;
  }, [contactError]);

  return (
    <form
      ref={formRef}
      class="lead"
      noValidate
      onSubmit={async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const name = String(data.get("name") ?? "").trim();
        const contact = String(data.get("contact") ?? "").trim();
        if (!name) return;
        if (!isValidContact(contact)) {
          setContactError(true);
          contactRef.current?.focus();
          return;
        }
        setState("sending");
        const ok = handoff
          ? await chat.handoff({ name, contact })
          : await chat.submitLead({ name, contact, question: String(data.get("question") ?? "") });
        if (ok) onDone();
        else setState("error");
      }}
    >
      <p class="lead-title">{handoff ? t("handoffTitle") : t("formTitle")}</p>
      {handoff && <p class="lead-note">{t("handoffNote")}</p>}
      <label>
        <span>{t("yourName")}</span>
        <input name="name" required maxLength={120} autoComplete="name" />
      </label>
      <label>
        <span>{t("contact")}</span>
        <input
          ref={contactRef}
          name="contact"
          required
          maxLength={200}
          placeholder={t("contactExample")}
          aria-invalid={contactError ? "true" : undefined}
          aria-describedby={contactError ? `contact-error-${kind}` : undefined}
          onInput={() => setContactError(false)}
        />
      </label>
      {contactError && (
        <p id={`contact-error-${kind}`} class="form-error" role="alert">
          {t("contactInvalid")}
        </p>
      )}
      {!handoff && (
        <label>
          <span>{t("question")}</span>
          <textarea name="question" rows={2} maxLength={2000} value={question} />
        </label>
      )}
      {state === "error" && (
        <p class="form-error" role="alert">
          {t("error")}
        </p>
      )}
      <div class="lead-actions">
        <button type="button" class="ghost" onClick={onDone}>
          {t("cancel")}
        </button>
        <button type="submit" class="primary" disabled={state === "sending"}>
          {handoff ? t("talkToPerson") : t("sendRequest")}
        </button>
      </div>
    </form>
  );
}

function MessageView(props: {
  message: ChatMessage;
  t: Translate;
  showSources: boolean;
  chat: ChatState;
  canHandoff: boolean;
  canLead: boolean;
  onForm: (kind: ContactKind) => void;
  onCite: (id: string) => void;
}) {
  const { message, t, showSources, chat, canHandoff, canLead, onForm, onCite } = props;
  const idPrefix = `src-${message.key}`;
  if (message.role === "system") {
    return <p class="notice">{message.content}</p>;
  }
  if (message.role === "visitor") {
    return <div class="bubble visitor">{message.content}</div>;
  }
  const waitingForFirstToken = message.streaming && !message.content;
  const actions = (message.actions ?? []).filter(
    (a) => (a === "handoff" && canHandoff) || (a === "lead" && canLead),
  );
  return (
    <div class={`turn ${message.role}`}>
      {message.role === "manager" && (
        <span class="author">
          <Icon name="person" size={13} /> {message.author || t("managerLabel")}
        </span>
      )}
      <div class="bubble answer" aria-busy={message.streaming ? "true" : undefined}>
        {waitingForFirstToken ? (
          <span class="typing" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        ) : (
          <Markdown text={message.content} onCite={(index) => onCite(`${idPrefix}-${index}`)} />
        )}
        {message.streaming && message.content && <span class="caret" aria-hidden="true" />}
      </div>
      {showSources && !message.streaming && message.sources && message.sources.length > 0 && (
        <Sources sources={message.sources} t={t} idPrefix={idPrefix} />
      )}
      {actions.length > 0 && (
        <div class="actions">
          {actions.includes("handoff") && (
            <button type="button" class="chip" onClick={() => onForm("handoff")}>
              <Icon name="person" size={15} />
              {t("talkToPerson")}
            </button>
          )}
          {actions.includes("lead") && (
            <button type="button" class="chip" onClick={() => onForm("lead")}>
              <Icon name="mail" size={15} />
              {t("leaveContact")}
            </button>
          )}
        </div>
      )}
      {message.rateable && (
        <div class="rate">
          <button
            type="button"
            aria-label={t("helpful")}
            onClick={() => void chat.rate(message.key, 1)}
          >
            <Icon name="up" size={15} />
          </button>
          <button
            type="button"
            aria-label={t("notHelpful")}
            onClick={() => void chat.rate(message.key, -1)}
          >
            <Icon name="down" size={15} />
          </button>
        </div>
      )}
    </div>
  );
}

function Widget(props: MountOptions & { register: (c: Controls) => void }) {
  const { apiBase, siteKey, config, inline = false, startOpen = false, register } = props;
  const { settings } = config;
  // The page language says more about the audience than the browser does.
  const lang: Lang = pickLanguage(
    settings.language,
    document.documentElement.lang || navigator.language,
  );
  const t = useMemo(() => translator(lang), [lang]);
  const texts = localizedTexts(settings, lang);
  const chat = useChat(apiBase, siteKey, lang, t, !inline);
  const [open, setOpen] = useState(inline || startOpen);
  const [form, setForm] = useState<ContactKind | null>(null);
  const [draft, setDraft] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    register({ open: () => setOpen(true), close: () => setOpen(false) });
  }, [register]);

  useEffect(() => {
    if (!inline) setOpenFlag(siteKey, open);
    // The admin preview remounts on every keystroke in the form; it must not steal focus.
    if (open && !inline) inputRef.current?.focus({ preventScroll: true });
  }, [open, inline, siteKey]);

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
    const last = chat.messages[chat.messages.length - 1];
    if (last && !last.streaming && last.role !== "visitor")
      setAnnouncement(last.content.slice(0, 300));
  }, [chat.messages, form]);

  const close = (): void => {
    setOpen(false);
    launcherRef.current?.focus();
  };

  const accent = settings.accent;
  const onAccent = readableOn(accent);
  const themeClass = settings.theme === "auto" ? "theme-auto" : `theme-${settings.theme}`;
  const style = `--accent:${accent};--on-accent:${onAccent};--radius:${settings.radius}px`;
  const empty = chat.messages.length === 0;
  const statusLine =
    chat.status === "waiting"
      ? t("waiting")
      : chat.status === "human" && chat.managerName
        ? t("joined", { name: chat.managerName })
        : texts.subtitle;

  return (
    <div class={`relay ${themeClass} ${settings.position} ${inline ? "inline" : ""}`} style={style}>
      {open && (
        <section
          class="panel"
          role={inline ? "region" : "dialog"}
          aria-label={texts.title}
          onKeyDown={(e) => {
            if (e.key === "Escape" && !inline) close();
          }}
        >
          <header class="head">
            <span class="avatar" aria-hidden="true">
              {initials(config.site_name)}
            </span>
            <div class="head-text">
              <h2>{texts.title}</h2>
              <p class={chat.status === "waiting" ? "pending" : ""}>{statusLine}</p>
            </div>
            {!inline && (
              <button type="button" class="icon-button" aria-label={t("close")} onClick={close}>
                <Icon name="close" />
              </button>
            )}
          </header>

          <div class="messages" ref={listRef}>
            <div class="turn bot">
              <div class="bubble answer">
                <Markdown text={texts.greeting} />
              </div>
            </div>
            {empty && texts.quick_questions.length > 0 && (
              <div class="quick">
                {texts.quick_questions.map((question) => (
                  <button type="button" class="chip" onClick={() => void chat.send(question)}>
                    {question}
                  </button>
                ))}
              </div>
            )}
            {chat.messages.map((message) => (
              <MessageView
                key={message.key}
                message={message}
                t={t}
                showSources={settings.show_sources}
                chat={chat}
                canHandoff={config.handoff_available && chat.status === "bot"}
                canLead={settings.collect_leads && chat.status === "bot"}
                onForm={setForm}
                onCite={(id) => {
                  const target = listRef.current?.querySelector<HTMLElement>(`[id="${id}"]`);
                  target?.scrollIntoView({ block: "nearest" });
                  target?.focus();
                }}
              />
            ))}
            {form && (
              <ContactForm
                key={form}
                kind={form}
                t={t}
                question={chat.lastQuestion}
                chat={chat}
                onDone={() => setForm(null)}
              />
            )}
          </div>

          <form
            class="composer"
            onSubmit={(event) => {
              event.preventDefault();
              const text = draft;
              setDraft("");
              void chat.send(text);
            }}
          >
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              maxLength={1000}
              placeholder={t("placeholder")}
              aria-label={t("placeholder")}
              onInput={(e) => {
                const el = e.currentTarget;
                setDraft(el.value);
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <button
              type="submit"
              class="send"
              aria-label={t("send")}
              disabled={!draft.trim() || chat.busy}
            >
              <Icon name="send" />
            </button>
          </form>
          <p class="foot">{t("poweredBy", { site: config.site_name })}</p>
          <div class="sr-only" aria-live="polite">
            {announcement}
          </div>
        </section>
      )}
      {!inline && (
        <button
          ref={launcherRef}
          type="button"
          class={`launcher ${open ? "is-open" : ""}`}
          aria-label={open ? t("close") : t("open")}
          aria-expanded={open}
          onClick={() => (open ? close() : setOpen(true))}
        >
          <Icon name={open ? "close" : "chat"} size={open ? 24 : 26} />
        </button>
      )}
    </div>
  );
}

export function mount(options: MountOptions): Controls {
  const style = document.createElement("style");
  style.textContent = styles;
  const container = document.createElement("div");
  // Inline previews fill whatever box the host gives them.
  if (options.inline) container.style.height = "100%";
  options.root.append(style, container);
  let controls: Controls = { open: () => undefined, close: () => undefined };
  render(
    <Widget
      {...options}
      register={(c) => {
        controls = c;
      }}
    />,
    container,
  );
  return {
    open: () => controls.open(),
    close: () => controls.close(),
  };
}

export type { WidgetConfig };
