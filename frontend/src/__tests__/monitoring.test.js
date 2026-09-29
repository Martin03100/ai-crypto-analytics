import { describe, expect, it } from "vitest";
import { initMonitoring, reportError, scrubEvent, scrubText } from "../utils/monitoring";

describe("monitoring", () => {
  it("is off without a DSN and reporting is a no-op", async () => {
    await expect(initMonitoring("")).resolves.toBe(false);
    expect(() => reportError(new Error("x"))).not.toThrow();
  });

  it("scrubs API keys and bearer tokens", () => {
    const out = scrubText("key AIzaSyA1234567890abcd and Bearer abc.def and sk-proj-ABCDEFGHIJ");
    expect(out).not.toMatch(/AIzaSyA1234567890abcd|abc\.def|ABCDEFGHIJ/);
    expect(out).toContain("[redacted]");
  });

  it("removes cookies and request bodies from events", () => {
    const event = scrubEvent({ request: { cookies: { a: 1 }, data: "password=x", headers: { Cookie: "c", Accept: "*/*" } },
      exception: { values: [{ value: "failed with sk-abcdefghijkl" }] } });
    expect(event.request.cookies).toBeUndefined();
    expect(event.request.data).toBeUndefined();
    expect(event.request.headers).toEqual({ Accept: "*/*" });
    expect(event.exception.values[0].value).toBe("failed with sk-[redacted]");
  });
});
