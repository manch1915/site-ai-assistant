import type { Session } from "./api";

// Storage can throw in private modes or sandboxed iframes; the chat must keep working anyway.
function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function loadSession(siteKey: string): Session | null {
  const raw = read(`relay:${siteKey}:session`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<Session>;
    return parsed.id && parsed.token ? { id: parsed.id, token: parsed.token } : null;
  } catch {
    return null;
  }
}

export function saveSession(siteKey: string, session: Session | null): void {
  write(`relay:${siteKey}:session`, session ? JSON.stringify(session) : null);
}

export function setOpenFlag(siteKey: string, open: boolean): void {
  write(`relay:${siteKey}:open`, open ? "1" : null);
}
