/** Onboarding tests. */

import { describe, expect, it, beforeEach } from "vitest";
import { hasSeenOnboarding, resetOnboarding } from "../components/OnboardingTour";

function makeMemoryStorage() {
  let store = {};
  return {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
    clear: () => { store = {}; },
  };
}
globalThis.localStorage = makeMemoryStorage();

describe("onboarding seen/reset localStorage helpers", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("reports not-seen before anything is stored", () => {
    expect(hasSeenOnboarding()).toBe(false);
  });

  it("reports seen once markOnboardingSeen's key is set directly", () => {
    localStorage.setItem("aca_onboarding_seen_v1", "1");
    expect(hasSeenOnboarding()).toBe(true);
  });

  it("resetOnboarding clears the seen flag so hasSeenOnboarding is false again", () => {
    localStorage.setItem("aca_onboarding_seen_v1", "1");
    expect(hasSeenOnboarding()).toBe(true);
    resetOnboarding();
    expect(hasSeenOnboarding()).toBe(false);
  });
  it("tracks the tour separately per user", () => {
    localStorage.setItem("aca_onboarding_seen_v1:1", "1");
    expect(hasSeenOnboarding(1)).toBe(true);
    expect(hasSeenOnboarding(2)).toBe(false);
    resetOnboarding(1);
    expect(hasSeenOnboarding(1)).toBe(false);
  });
});
