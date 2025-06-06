import { useSyncExternalStore } from "react";

// A tiny localStorage-backed store, so React reads it during render instead of
// copying it into state from an effect.
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice just won't survive a reload */
  }
  listeners.forEach((listener) => listener());
}

export function useStored(key: string, fallback: () => string): string {
  return useSyncExternalStore(
    subscribe,
    () => readStored(key) ?? fallback(),
    () => fallback(),
  );
}
