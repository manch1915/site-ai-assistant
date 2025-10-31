import { describe, expect, it } from "vitest";

import { isValidContact } from "../src/contact";

describe("isValidContact", () => {
  it("accepts a Telegram username, a phone or an email", () => {
    expect(isValidContact("@narcisbin")).toBe(true);
    expect(isValidContact("t.me/narcisbin")).toBe(true);
    expect(isValidContact("+374 (91) 12-34-56")).toBe(true);
    expect(isValidContact("anna@example.com")).toBe(true);
  });

  it("rejects text a manager couldn't write back to", () => {
    expect(isValidContact("call me")).toBe(false);
    expect(isValidContact("12345")).toBe(false);
    expect(isValidContact("@ab")).toBe(false);
  });
});
