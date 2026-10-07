import { describe, expect, it } from "vitest";
import { injectMeta, metaFor } from "../../netlify/edge-functions/og.js";

const HTML = `<html><head>
    <meta property="og:title" content="AI Crypto Analytics" />
    <meta property="og:image" content="https://site/og-image.png" />
    <meta name="twitter:image" content="https://site/og-image.png" />
  </head><body></body></html>`;

describe("share preview edge function", () => {
  it("targets only shared forecasts and the track record", () => {
    expect(metaFor(new URL("https://site/share/abcdefghij123456")).image).toBe("https://site/api/public/forecasts/abcdefghij123456/card.png");
    expect(metaFor(new URL("https://site/track-record")).image).toBe("https://site/api/public/track-record/card.png");
    expect(metaFor(new URL("https://site/share/short"))).toBeNull();
    expect(metaFor(new URL("https://site/dashboard"))).toBeNull();
  });

  it("replaces existing tags and adds missing ones", () => {
    const meta = metaFor(new URL("https://site/share/abcdefghij123456"));
    const out = injectMeta(HTML, meta);
    expect(out).toContain('<meta property="og:image" content="https://site/api/public/forecasts/abcdefghij123456/card.png" />');
    expect(out).not.toContain("og-image.png");
    expect(out).toContain('<meta property="og:url"');
    expect(out).toContain('<meta name="robots" content="noindex" />');
    expect(out.match(/og:title/g)).toHaveLength(1);
  });

  it("escapes attribute values", () => {
    const out = injectMeta(HTML, { title: 'a "b" <c>', description: "d", image: "i", url: "u" });
    expect(out).toContain('content="a &quot;b&quot; &lt;c>"');
  });
});
