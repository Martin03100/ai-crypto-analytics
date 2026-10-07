import { describe, expect, it } from "vitest";
import { humanizeError } from "../i18n/errorMessages";
import { notificationText } from "../utils/notifications";

const t = (k, p) => `${k}${p ? JSON.stringify(p) : ""}`;

describe("weekly challenge texts", () => {
  it("maps backend challenge errors", () => {
    for (const [msg, key] of [
      ["Tento týždeň už máš tip.", "already have a tip"],
      ["Tipy na tento týždeň sú už uzavreté.", "already closed"],
      ["Tip je mimo rozumného rozsahu.", "reasonable range"],
      ["Výzvu sa teraz nepodarilo načítať. Skús to neskôr.", "can't be loaded"],
    ]) expect(humanizeError(msg, "en")).toContain(key);
  });
  it("renders the challenge_won notification", () => {
    const text = notificationText({ kind: "challenge_won", data: { coin: "BTC", price: 65000 } }, t);
    expect(text).toContain("notif.challengeWon");
    expect(text).toContain("BTC");
  });
});
