/**
 * Netlify Edge Function: gives shared forecasts and the track record their own preview image,
 * so a link posted on X, Reddit, Discord or WhatsApp shows the result instead of the generic card.
 */

const TEXT = {
  share: {
    title: "AI crypto forecast, checked against reality",
    description: "See what the AI predicted and whether it was right. AI Crypto Analytics.",
  },
  track: {
    title: "Which AI predicts crypto best? Public track record",
    description: "Live accuracy of Gemini, GPT, Claude, DeepSeek and Grok on real crypto prices.",
  },
};

const escapeAttr = (v) => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

function setMeta(html, attr, key, value) {
  const tag = `<meta ${attr}="${key}" content="${escapeAttr(value)}" />`;
  const re = new RegExp(`<meta\\s+${attr}="${key.replace(/[:.]/g, "\\$&")}"[^>]*>`, "i");
  return re.test(html) ? html.replace(re, tag) : html.replace("</head>", `    ${tag}\n  </head>`);
}

export function metaFor(url) {
  const share = url.pathname.match(/^\/share\/([A-Za-z0-9_-]{16,64})\/?$/);
  if (share) {
    return { ...TEXT.share, image: `${url.origin}/api/public/forecasts/${share[1]}/card.png`, url: url.href, noindex: true };
  }
  if (url.pathname.replace(/\/$/, "") === "/track-record") {
    return { ...TEXT.track, image: `${url.origin}/api/public/track-record/card.png`, url: `${url.origin}/track-record` };
  }
  return null;
}

export function injectMeta(html, meta) {
  let out = html;
  for (const [attr, key, value] of [
    ["property", "og:title", meta.title], ["property", "og:description", meta.description],
    ["property", "og:image", meta.image], ["property", "og:url", meta.url],
    ["name", "twitter:title", meta.title], ["name", "twitter:description", meta.description],
    ["name", "twitter:image", meta.image],
  ]) {
    out = setMeta(out, attr, key, value);
  }
  if (meta.noindex) out = setMeta(out, "name", "robots", "noindex");
  return out;
}

export default async function handler(request, context) {
  const response = await context.next();
  const meta = metaFor(new URL(request.url));
  if (!meta || !(response.headers.get("content-type") || "").includes("text/html")) return response;
  const headers = new Headers(response.headers);
  headers.delete("content-length");
  return new Response(injectMeta(await response.text(), meta), { status: response.status, headers });
}

export const config = { path: ["/share/*", "/track-record"] };
