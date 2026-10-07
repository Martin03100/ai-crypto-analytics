import { describe, expect, it } from "vitest";
import { alternates, injectCoinMeta, pageFor, snippet } from "../../netlify/edge-functions/coin.js";
import { SEO_COINS, coinBySlug, coinPath, langFromPath } from "../utils/seoCoins";

const HTML = `<html lang="en"><head><title>AI Crypto Analytics</title><meta name="description" content="x" /></head><body><div id="root"></div></body></html>`;

describe("seo coins", () => {
  it("has 20 unique coins and slugs", () => {
    expect(SEO_COINS).toHaveLength(20);
    expect(new Set(SEO_COINS.map((c) => c.slug)).size).toBe(20);
  });
  it("resolves slugs, paths and languages", () => {
    expect(coinBySlug("Bitcoin").coin).toBe("BTC");
    expect(coinBySlug("nope")).toBeNull();
    expect(coinPath("sk", "solana")).toBe("/sk/predikcia/solana");
    expect(langFromPath("/cs/predikce/xrp")).toBe("cs");
    expect(langFromPath("/prediction")).toBe("en");
  });
});

describe("coin edge function", () => {
  it("matches index, coin and rejects unknown slugs", () => {
    expect(pageFor("/prediction/")).toMatchObject({ lang: "en", coin: null });
    expect(pageFor("/sk/predikcia/ethereum").coin.coin).toBe("ETH");
    expect(pageFor("/prediction/unknown")).toBeNull();
    expect(pageFor("/predictionx")).toBeNull();
  });
  it("lists all three language alternates", () => {
    const alts = alternates(pageFor("/cs/predikce/bitcoin"));
    expect(alts.map((a) => a.href)).toEqual([
      "https://aicryptopredictor.netlify.app/prediction/bitcoin",
      "https://aicryptopredictor.netlify.app/sk/predikcia/bitcoin",
      "https://aicryptopredictor.netlify.app/cs/predikce/bitcoin",
    ]);
  });
  it("injects title, canonical, hreflang, JSON-LD and snippet", () => {
    const page = pageFor("/sk/predikcia/bitcoin");
    const out = injectCoinMeta(HTML, page, { price: 65000, outlook: [{ horizon: "24h", low: 64000, high: 66000 }] });
    expect(out).toContain('<html lang="sk"');
    expect(out).toContain("<title>Predikcia ceny Bitcoin (BTC)");
    expect(out).toContain('rel="canonical" href="https://aicryptopredictor.netlify.app/sk/predikcia/bitcoin"');
    expect(out).toContain('hreflang="x-default"');
    expect(out).toContain("application/ld+json");
    expect(out).toContain("$65,000");
    expect(out).toContain("$64,000 – $66,000");
  });
  it("escapes and survives missing data", () => {
    const s = snippet(pageFor("/prediction/pepe"), null);
    expect(s).toContain("Pepe");
    expect(s).not.toContain("undefined");
  });
});
