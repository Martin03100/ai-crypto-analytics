import { describe, expect, it } from "vitest";
import { translate } from "../i18n/translations";
import { notificationText, timeAgo } from "../utils/notifications";

const t = (key, params) => translate(key, "en", params);

describe("notifications", () => {
  it("describes each kind", () => {
    expect(notificationText({ kind: "forecast_evaluated", data: { coin: "BTC", horizon: "4h", direction_correct: true, accuracy_pct: 98.1 } }, t))
      .toBe("✓ Your BTC 4H forecast got the direction right (98.1% accuracy).");
    expect(notificationText({ kind: "duel_settled", data: { outcome: "loss" } }, t)).toContain("AI won");
    expect(notificationText({ kind: "referral_reward", data: { days: 30 } }, t)).toContain("30 days");
    expect(notificationText({ kind: "price_alert", data: { coin: "ETH", direction: "below", price: 2450.5 } }, t))
      .toBe("🔔 ETH fell below your alert — now $2,450.50.");
    expect(notificationText({ kind: "unknown", data: {} }, t)).toBe("");
  });

  it("formats relative time", () => {
    const now = Date.parse("2026-10-07T12:00:00Z");
    expect(timeAgo("2026-10-07T11:59:40Z", t, now)).toBe("just now");
    expect(timeAgo("2026-10-07T11:15:00Z", t, now)).toBe("45 min ago");
    expect(timeAgo("2026-10-07T06:00:00Z", t, now)).toBe("6h ago");
    expect(timeAgo("2026-10-04T12:00:00Z", t, now)).toBe("3d ago");
  });
});
