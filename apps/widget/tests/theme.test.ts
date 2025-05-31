import { describe, expect, it } from "vitest";

import { readableOn } from "../src/color";
import { pickLanguage, translator } from "../src/i18n";

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
