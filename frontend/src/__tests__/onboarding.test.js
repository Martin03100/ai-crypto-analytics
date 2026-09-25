import { describe, expect, it, beforeEach } from "vitest";
import { hasSeenOnboarding, resetOnboarding } from "../components/OnboardingTour";

// Testovacie prostredie bezi v Node (viz vite.config.js), nie jsdom, takze
// localStorage tu z principu neexistuje - pre tento jeden subor si ho
// nahradime jednoduchou pamatovou nahradou namiesto menenia zdielanej
// konfiguracie testov (ktora by mohla ovplyvnit ostatne testy).
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
});
