/**
 * Netlify Edge Function: server-side title, description, canonical, hreflang and a short text snippet
 * for the public coin pages, so search engines and link previews see real content without running JS.
 */

import { SEO_COINS, SEO_LANGS, coinBySlug, langFromPath } from "../../src/utils/seoCoins.js";

const SITE = "https://aicryptopredictor.netlify.app";
const FETCH_TIMEOUT_MS = 1500;

const TEXT = {
  en: {
    title: (n, c) => `${n} (${c}) price prediction — AI forecast & accuracy`,
    desc: (n) => `Today's ${n} price outlook from a statistical model and 5 AI models, with live signals and a public record of how accurate past forecasts were.`,
    indexTitle: "Crypto price predictions — 20 coins, AI forecasts checked against reality",
    indexDesc: "Daily price outlook for Bitcoin, Ethereum, Solana and 17 more coins, with the measured accuracy of every model.",
    price: "Price", outlook: "24h outlook", disclaimer: "Not financial advice.",
  },
  sk: {
    title: (n, c) => `Predikcia ceny ${n} (${c}) — AI prognóza a presnosť`,
    desc: (n) => `Dnešný výhľad ceny ${n} zo štatistického modelu a 5 AI modelov, so živými signálmi a verejným záznamom presnosti minulých prognóz.`,
    indexTitle: "Predikcie cien kryptomien — 20 mincí, AI prognózy overené realitou",
    indexDesc: "Denný výhľad ceny Bitcoinu, Etherea, Solany a ďalších 17 mincí aj s nameranou presnosťou každého modelu.",
    price: "Cena", outlook: "Výhľad 24 h", disclaimer: "Nejde o investičné poradenstvo.",
  },
  cs: {
    title: (n, c) => `Predikce ceny ${n} (${c}) — AI prognóza a přesnost`,
    desc: (n) => `Dnešní výhled ceny ${n} ze statistického modelu a 5 AI modelů, s živými signály a veřejným záznamem přesnosti minulých prognóz.`,
    indexTitle: "Predikce cen kryptoměn — 20 mincí, AI prognózy ověřené realitou",
    indexDesc: "Denní výhled ceny Bitcoinu, Etherea, Solany a dalších 17 mincí včetně naměřené přesnosti každého modelu.",
    price: "Cena", outlook: "Výhled 24 h", disclaimer: "Nejedná se o investiční poradenství.",
  },
};

const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function setTag(html, re, tag) {
  return re.test(html) ? html.replace(re, tag) : html.replace("</head>", `    ${tag}\n  </head>`);
}

function setMeta(html, attr, key, value) {
  const re = new RegExp(`<meta\\s+${attr}="${key.replace(/[:.]/g, "\\$&")}"[^>]*>`, "i");
  return setTag(html, re, `<meta ${attr}="${key}" content="${esc(value)}" />`);
}

/** Works out what the page is: the index or one coin, in which language. null for unknown slugs. */
export function pageFor(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";
  const lang = langFromPath(path + "/");
  const base = SEO_LANGS[lang];
  if (path === base) return { lang, coin: null, path };
  if (!path.startsWith(`${base}/`)) return null;
  const coin = coinBySlug(path.slice(base.length + 1));
  return coin ? { lang, coin, path } : null;
}

export function alternates(page) {
  return Object.entries(SEO_LANGS).map(([lang, base]) => {
    const href = `${SITE}${base}${page.coin ? `/${page.coin.slug}` : ""}`;
    return { hreflang: lang === "cs" ? "cs" : lang, href };
  });
}

function fmtPrice(p) {
  if (!Number.isFinite(p)) return null;
  return `$${p >= 1 ? p.toLocaleString("en-US", { maximumFractionDigits: 2 }) : p.toPrecision(4)}`;
}

/** Plain HTML shown before React mounts and readable by crawlers; React replaces it on load. */
export function snippet(page, data) {
  const t = TEXT[page.lang];
  if (!page.coin) {
    const base = SEO_LANGS[page.lang];
    const links = SEO_COINS.map((c) => `<li><a href="${base}/${c.slug}">${esc(c.name)} (${c.coin})</a></li>`).join("");
    return `<main class="seo-snippet"><h1>${esc(t.indexTitle)}</h1><p>${esc(t.indexDesc)}</p><ul>${links}</ul></main>`;
  }
  const { coin, name } = page.coin;
  const lines = [`<h1>${esc(t.title(name, coin))}</h1>`, `<p>${esc(t.desc(name))}</p>`];
  const price = fmtPrice(Number(data?.price));
  if (price) lines.push(`<p>${esc(t.price)}: ${esc(price)}</p>`);
  const o = Array.isArray(data?.outlook) ? data.outlook.find((x) => x.horizon === "24h") : null;
  const low = fmtPrice(Number(o?.low)), high = fmtPrice(Number(o?.high));
  if (low && high) lines.push(`<p>${esc(t.outlook)}: ${esc(low)} – ${esc(high)}</p>`);
  lines.push(`<p><small>${esc(t.disclaimer)}</small></p>`);
  return `<main class="seo-snippet">${lines.join("")}</main>`;
}

export function injectCoinMeta(html, page, data) {
  const t = TEXT[page.lang];
  const title = page.coin ? t.title(page.coin.name, page.coin.coin) : t.indexTitle;
  const desc = page.coin ? t.desc(page.coin.name) : t.indexDesc;
  const url = `${SITE}${page.path}`;
  let out = html.replace(/<title>[^<]*<\/title>/i, `<title>${esc(title)}</title>`);
  out = out.replace(/<html([^>]*)\blang="[^"]*"/i, `<html$1lang="${page.lang}"`);
  out = setMeta(out, "name", "description", desc);
  for (const [attr, key, value] of [
    ["property", "og:title", title], ["property", "og:description", desc], ["property", "og:url", url],
    ["name", "twitter:title", title], ["name", "twitter:description", desc],
  ]) out = setMeta(out, attr, key, value);
  out = setTag(out, /<link\s+rel="canonical"[^>]*>/i, `<link rel="canonical" href="${url}" />`);
  out = out.replace(/\s*<link rel="alternate" hreflang="[^"]*"[^>]*>/gi, "");
  const alts = alternates(page).map((a) => `<link rel="alternate" hreflang="${a.hreflang}" href="${a.href}" />`);
  alts.push(`<link rel="alternate" hreflang="x-default" href="${alternates(page)[0].href}" />`);
  out = out.replace("</head>", `    ${alts.join("\n    ")}\n  </head>`);
  if (page.coin) {
    const ld = {
      "@context": "https://schema.org", "@type": "WebPage", name: title, description: desc, url, inLanguage: page.lang,
      about: { "@type": "Thing", name: page.coin.name, alternateName: page.coin.coin },
    };
    const json = JSON.stringify(ld).replace(/</g, "\\u003c");
    out = out.replace("</head>", `    <script type="application/ld+json">${json}</script>\n  </head>`);
  }
  return out.replace('<div id="root"></div>', `<div id="root">${snippet(page, data)}</div>`);
}

async function fetchData(origin, coin) {
  try {
    const res = await fetch(`${origin}/api/public/coin/${coin}`, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function handler(request, context) {
  const url = new URL(request.url);
  const page = pageFor(url.pathname);
  if (!page) return context.next();
  const [response, data] = await Promise.all([
    context.next(),
    page.coin ? fetchData(url.origin, page.coin.coin) : Promise.resolve(null),
  ]);
  if (!(response.headers.get("content-type") || "").includes("text/html")) return response;
  const headers = new Headers(response.headers);
  headers.delete("content-length");
  headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  return new Response(injectCoinMeta(await response.text(), page, data), { status: response.status, headers });
}

export const config = { path: ["/prediction", "/prediction/*", "/sk/predikcia", "/sk/predikcia/*", "/cs/predikce", "/cs/predikce/*"] };
