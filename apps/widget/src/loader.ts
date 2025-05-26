/**
 * The script sites paste in. It stays tiny: draws the launcher button straight away and
 * fetches the chat itself only when the visitor shows interest, so the host page's
 * performance score doesn't pay for a chat nobody opened.
 */
import { readableOn } from "./color";
import type { MountOptions, WidgetConfig } from "./types";

interface AppModule {
  mount(options: MountOptions): { open(): void; close(): void };
}

interface RelayApi {
  open(): void;
  close(): void;
  preview(element: HTMLElement, config: WidgetConfig): Promise<void>;
}

declare global {
  interface Window {
    Relay?: RelayApi;
  }
}

const ICON =
  '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>';

const script =
  (document.currentScript as HTMLScriptElement | null) ??
  document.querySelector<HTMLScriptElement>("script[data-key][src*='widget.js']");
const siteKey = script?.dataset.key ?? "";
const apiBase = (
  script?.dataset.api ?? (script ? new URL(script.src).origin : location.origin)
).replace(/\/$/, "");
const manual = script?.dataset.manual !== undefined;
const openFlag = `relay:${siteKey}:open`;

let appModule: Promise<AppModule> | null = null;
function loadApp(): Promise<AppModule> {
  appModule ??= import(/* @vite-ignore */ `${apiBase}/widget-app.js`) as Promise<AppModule>;
  return appModule;
}

function readFlag(): boolean {
  try {
    return localStorage.getItem(openFlag) === "1";
  } catch {
    return false;
  }
}

async function boot(): Promise<void> {
  if (!siteKey) return;
  let config: WidgetConfig;
  try {
    const response = await fetch(`${apiBase}/v1/widget/${siteKey}/config`);
    if (!response.ok) throw new Error(String(response.status));
    config = (await response.json()) as WidgetConfig;
  } catch (error) {
    console.warn("[relay] widget is not available on this site:", error);
    return;
  }

  const host = document.createElement("div");
  host.id = "relay-widget";
  host.style.cssText = "position:relative;z-index:2147483000";
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  const side = config.settings.position === "left" ? "left" : "right";
  // The API validates the colour already; checking again keeps this innerHTML safe on its own.
  const accent = /^#[0-9a-f]{6}$/i.test(config.settings.accent)
    ? config.settings.accent
    : "#0e7c66";
  root.innerHTML = `<style>
    .launcher{position:fixed;bottom:20px;${side}:20px;width:56px;height:56px;border-radius:50%;border:0;
    background:${accent};color:${readableOn(accent)};display:grid;place-items:center;cursor:pointer;
    box-shadow:0 8px 24px -6px rgba(0,0,0,.35);transition:transform .15s ease}
    .launcher:hover{transform:scale(1.05)}.launcher:focus-visible{outline:3px solid ${accent};outline-offset:3px}
    @media (prefers-reduced-motion:reduce){.launcher{transition:none}}
  </style><button class="launcher" type="button" aria-label="Open chat" aria-expanded="false">${ICON}</button>`;
  const button = root.querySelector("button");

  let controls: { open(): void; close(): void } | null = null;
  const start = async (startOpen: boolean): Promise<void> => {
    if (controls) {
      if (startOpen) controls.open();
      return;
    }
    const app = await loadApp();
    root.innerHTML = "";
    controls = app.mount({ apiBase, siteKey, root, config, startOpen });
  };

  button?.addEventListener("pointerenter", () => void loadApp(), { once: true });
  button?.addEventListener("focus", () => void loadApp(), { once: true });
  button?.addEventListener("click", () => void start(true));

  window.Relay = {
    open: () => void start(true),
    close: () => controls?.close(),
    preview: async (element, previewConfig) => {
      const app = await loadApp();
      const previewRoot = element.shadowRoot ?? element.attachShadow({ mode: "open" });
      previewRoot.innerHTML = "";
      app.mount({ apiBase, siteKey, root: previewRoot, config: previewConfig, inline: true });
    },
  };

  if (readFlag()) await start(true);
}

if (manual) {
  window.Relay = {
    open: () => undefined,
    close: () => undefined,
    preview: async (element, config) => {
      const app = await loadApp();
      const root = element.shadowRoot ?? element.attachShadow({ mode: "open" });
      root.innerHTML = "";
      app.mount({ apiBase, siteKey, root, config, inline: true });
    },
  };
} else if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => void boot());
} else {
  void boot();
}
