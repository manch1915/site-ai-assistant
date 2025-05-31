import { render } from "preact";
import { describe, expect, it, vi } from "vitest";

import { Markdown, parseBlocks, safeUrl } from "../src/markdown";

function html(text: string, onCite?: (n: number) => void): HTMLElement {
  const host = document.createElement("div");
  render(<Markdown text={text} onCite={onCite} />, host);
  return host;
}

describe("Markdown", () => {
  it("renders paragraphs, lists and quotes", () => {
    expect(parseBlocks("Intro\n\n- one\n- two\n\n> quoted").map((b) => b.kind)).toEqual([
      "p",
      "ul",
      "quote",
    ]);
  });

  it("never turns model output into HTML", () => {
    const host = html('<img src=x onerror="alert(1)"> **bold**');
    expect(host.querySelector("img")).toBeNull();
    expect(host.querySelector("strong")?.textContent).toBe("bold");
    expect(host.textContent).toContain("<img");
  });

  it("only links http and https URLs", () => {
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    const host = html("[click](javascript:alert(1)) and https://ohmsolder.example/prices");
    const links = [...host.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(links).toEqual(["https://ohmsolder.example/prices"]);
  });

  it("turns [n] into citation buttons", () => {
    const onCite = vi.fn();
    const host = html("Screens cost €189 [1].", onCite);
    host.querySelector<HTMLButtonElement>("button.cite")?.click();
    expect(onCite).toHaveBeenCalledWith(1);
  });
});
