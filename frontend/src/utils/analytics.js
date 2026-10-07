/** Optional cookieless analytics (Umami, off unless VITE_UMAMI_WEBSITE_ID is set) and UTM capture. */

const UTM_STORAGE_KEY = "aca_utm_source";
const UMAMI_SCRIPT = "https://cloud.umami.is/script.js";
const SOURCE_RE = /^[a-z0-9_.-]{1,32}$/;

export function parseUtmSource(search) {
  try {
    const value = new URLSearchParams(search || "").get("utm_source");
    const clean = (value || "").trim().toLowerCase();
    return SOURCE_RE.test(clean) ? clean : null;
  } catch {
    return null;
  }
}

/** Remembers the visit's source for this tab, so a waitlist sign-up can be attributed. */
export function rememberUtmSource(search = typeof window !== "undefined" ? window.location.search : "") {
  const source = parseUtmSource(search);
  if (!source) return;
  try {
    sessionStorage.setItem(UTM_STORAGE_KEY, source);
  } catch {
    /* best-effort */
  }
}

export function getUtmSource() {
  try {
    const value = sessionStorage.getItem(UTM_STORAGE_KEY);
    return value && SOURCE_RE.test(value) ? value : null;
  } catch {
    return null;
  }
}

/** Share links carry a secret token in the path; analytics only ever see "/share/…". */
export function redactPayload(type, payload) {
  if (payload && typeof payload.url === "string") {
    return { ...payload, url: payload.url.replace(/\/share\/[^/?#]+/, "/share/…") };
  }
  return payload;
}

export function initAnalytics(websiteId = import.meta.env.VITE_UMAMI_WEBSITE_ID) {
  if (!websiteId || typeof document === "undefined" || document.querySelector("script[data-website-id]")) return false;
  const script = document.createElement("script");
  script.defer = true;
  script.src = UMAMI_SCRIPT;
  script.dataset.websiteId = websiteId;
  script.dataset.doNotTrack = "true";
  window.acaAnalyticsBeforeSend = redactPayload;
  script.dataset.beforeSend = "acaAnalyticsBeforeSend";
  document.head.appendChild(script);
  return true;
}

export function trackEvent(name, data) {
  try {
    window.umami?.track?.(name, data);
  } catch {
    /* analytics must never break the app */
  }
}
