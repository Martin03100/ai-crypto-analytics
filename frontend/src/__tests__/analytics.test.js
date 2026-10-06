import { afterEach, describe, expect, it, vi } from "vitest";
import { getUtmSource, initAnalytics, parseUtmSource, redactPayload, rememberUtmSource, trackEvent } from "../utils/analytics";

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)) };
}

afterEach(() => vi.unstubAllGlobals());

describe("analytics", () => {
  it("reads and normalises utm_source", () => {
    expect(parseUtmSource("?utm_source=TikTok&utm_medium=social")).toBe("tiktok");
    expect(parseUtmSource("?utm_medium=social")).toBeNull();
    expect(parseUtmSource("?utm_source=<script>")).toBeNull();
    expect(parseUtmSource("?utm_source=" + "a".repeat(40))).toBeNull();
    expect(parseUtmSource("")).toBeNull();
  });

  it("remembers the source for the rest of the visit", () => {
    vi.stubGlobal("sessionStorage", memoryStorage());
    rememberUtmSource("?utm_source=instagram");
    rememberUtmSource("?foo=bar"); // later pages without UTM keep the first source
    expect(getUtmSource()).toBe("instagram");
  });

  it("never throws when storage is blocked", () => {
    vi.stubGlobal("sessionStorage", { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } });
    expect(() => rememberUtmSource("?utm_source=x")).not.toThrow();
    expect(getUtmSource()).toBeNull();
  });

  it("is off without a website id and events are a no-op", () => {
    expect(initAnalytics("")).toBe(false);
    expect(() => trackEvent("waitlist-signup")).not.toThrow();
  });

  it("hides share-link tokens from analytics", () => {
    const out = redactPayload("event", { url: "/share/AbC123secretToken_xyz?utm_source=x", title: "t" });
    expect(out.url).toBe("/share/…?utm_source=x");
    expect(out.title).toBe("t");
    expect(redactPayload("event", { url: "/track-record" }).url).toBe("/track-record");
  });
});
