import { describe, expect, it } from "vitest";

import { readableOn } from "../src/color";
import { localizedTexts } from "../src/app";
import { pickLanguage, translator } from "../src/i18n";
import type { WidgetSettings } from "../src/types";

describe("readableOn", () => {
  it("puts white text on dark accents and dark text on light ones", () => {
    expect(readableOn("#0F5C4A")).toBe("#ffffff");
    expect(readableOn("#F2C230")).toBe("#111315");
    expect(readableOn("not a colour")).toBe("#ffffff");
  });
});

describe("language", () => {
  it("follows the owner's choice, then the page", () => {
    expect(pickLanguage("ru", "en-US")).toBe("ru");
    expect(pickLanguage("auto", "ru-RU")).toBe("ru");
    expect(pickLanguage("auto", "pt-PT")).toBe("en");
  });

  it("fills placeholders", () => {
    expect(translator("en")("joined", { name: "Inês" })).toBe("Inês is in the chat");
    expect(translator("ru")("joined", { name: "Инес" })).toBe("Инес в чате");
  });
});

describe("localizedTexts", () => {
  const settings = {
    title: "Ask about Levon",
    subtitle: "Answers from narcisbin.com",
    greeting: "Hi!",
    quick_questions: ["What has he built?"],
    ru: { title: "", subtitle: "", greeting: "Привет!", quick_questions: ["Что он делал?"] },
  } as unknown as WidgetSettings;

  it("uses Russian texts for a Russian interface and falls back field by field", () => {
    const texts = localizedTexts(settings, "ru");
    expect(texts.greeting).toBe("Привет!");
    expect(texts.title).toBe("Ask about Levon");
    expect(texts.quick_questions).toEqual(["Что он делал?"]);
  });

  it("ignores them for an English interface", () => {
    expect(localizedTexts(settings, "en").greeting).toBe("Hi!");
  });
});
