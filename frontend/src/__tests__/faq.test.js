/** FAQ content: complete in every language and free of Premium wording while Premium is off. */

import { describe, expect, it } from "vitest";
import { FAQ } from "../data/faq";

const LANGS = ["en", "sk", "cs", "de", "pl"];

describe("FAQ", () => {
  it("has every question and answer in every language", () => {
    for (const f of FAQ) {
      for (const lang of LANGS) {
        expect(f.q[lang], `${f.id} q ${lang}`).toBeTruthy();
        expect(f.a[lang], `${f.id} a ${lang}`).toBeTruthy();
        if (f.aPremium) expect(f.aPremium[lang], `${f.id} aPremium ${lang}`).toBeTruthy();
      }
    }
  });

  it("never mentions Premium, prices or payments in the answers shown while Premium is off", () => {
    for (const f of FAQ) {
      for (const lang of LANGS) expect(`${f.q[lang]} ${f.a[lang]}`, `${f.id} ${lang}`).not.toMatch(/premium|prémi|€|stripe/i);
    }
  });
});
