import { afterEach, describe, expect, it, vi } from "vitest";
import { captureReferralCode, getReferralCode } from "../utils/referral";

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)) };
}

afterEach(() => vi.unstubAllGlobals());

describe("referral code", () => {
  it("keeps a valid ?ref= code until sign-up", () => {
    vi.stubGlobal("localStorage", memoryStorage());
    captureReferralCode("?ref=abcd2345&utm_source=tiktok");
    captureReferralCode("?ref=<bad>");
    expect(getReferralCode()).toBe("ABCD2345");
  });

  it("is empty without storage", () => {
    vi.stubGlobal("localStorage", { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } });
    expect(() => captureReferralCode("?ref=ABCD2345")).not.toThrow();
    expect(getReferralCode()).toBeNull();
  });
});
