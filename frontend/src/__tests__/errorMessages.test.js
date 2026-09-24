import { describe, expect, it } from "vitest";
import { humanizeError } from "../i18n/errorMessages";

describe("humanizeError()", () => {
  it("recognizes an exact backend Slovak message and translates it to English", () => {
    const raw = "Nespravne pouzivatelske meno alebo heslo.";
    expect(humanizeError(raw, "en")).toBe("Incorrect username or password.");
  });

  it("recognizes the same backend message and translates it to Slovak (identity-ish, but via the key)", () => {
    const raw = "Nespravne pouzivatelske meno alebo heslo.";
    expect(humanizeError(raw, "sk")).toMatch(/Nesprávne/);
  });

  it("interpolates the retry-after seconds from a rate-limit message", () => {
    const raw = "Príliš veľa požiadaviek. Skús to znova o 42s.";
    const result = humanizeError(raw, "en");
    expect(result).toContain("42");
    expect(result).not.toBe(raw); // must not leak the raw Slovak text to an EN user
  });

  it("interpolates the lockout minutes from the account-locked message", () => {
    const raw = "Účet je dočasne uzamknutý pre priveľa neúspešných pokusov. Skús to znova o 15 min.";
    const result = humanizeError(raw, "en");
    expect(result).toContain("15");
  });

  it("recognizes a raw technical provider error (401) and returns a friendly message", () => {
    const raw = "401 Client Error: Unauthorized for url: https://api.example.com/v1/chat";
    const result = humanizeError(raw, "en");
    expect(result).not.toContain("Client Error");
    expect(result.length).toBeLessThan(120);
  });

  it("falls back to an HTTP-status-based message when the status is known but no text pattern matches", () => {
    const err = { message: "some totally unexpected wording", status: 401 };
    const result = humanizeError(err, "en");
    expect(result).not.toBe(err.message);
  });

  it("never leaks a completely unrecognized raw error to the user", () => {
    const result = humanizeError("TypeError: Cannot read properties of undefined (reading 'foo')", "en");
    expect(result).not.toContain("TypeError");
    expect(result).not.toContain("undefined");
  });

  it("handles a missing/empty error gracefully", () => {
    expect(() => humanizeError(undefined, "en")).not.toThrow();
    expect(() => humanizeError("", "en")).not.toThrow();
  });

  it("shortens a real Gemini 429 quota-exceeded dump to a short translated message", () => {
    const raw = "Gemini API chyba: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details.', 'status': 'RESOURCE_EXHAUSTED'}}";
    const result = humanizeError(raw, "en");
    expect(result).toBe("You've hit the AI provider's rate limit. Wait a moment and try again.");
    expect(result.length).toBeLessThan(80);
  });

  it("accepts an Error-like object with .message as well as a plain string", () => {
    const err = new Error("Nespravne pouzivatelske meno alebo heslo.");
    expect(humanizeError(err, "en")).toBe("Incorrect username or password.");
  });
});
