/** API client. */

const BASE = "/api";
const CSRF_COOKIE_NAME = "aca_csrf";
const LANG_STORAGE_KEY = "aca_lang";
const VALID_LANGS = ["en", "sk", "cs"];

function currentLang() {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    return VALID_LANGS.includes(stored) ? stored : "en";
  } catch {
    return "en";
  }
}

function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function extractDetailMessage(detail) {
  if (!detail) return undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first?.msg) return first.msg;
    return undefined;
  }
  if (typeof detail === "object") return detail.message || detail.msg || undefined;
  return undefined;
}

const AUTH_401_EXEMPT = ["/auth/login", "/auth/register", "/auth/me", "/auth/forgot-password", "/auth/verify-reset-code", "/auth/reset-password"];
export const SESSION_EXPIRED_EVENT = "aca:session-expired";

// Generous on purpose: a sleeping free-tier backend can take close to a minute to wake up.
const DEFAULT_TIMEOUT_MS = 60_000;
// AI calls wait for the model to finish generating.
export const AI_TIMEOUT_MS = 90_000;

function apiError(message, extra = {}) {
  const err = new Error(message);
  Object.assign(err, extra);
  return err;
}

async function request(path, { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (method !== "GET") {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      credentials: "include",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller?.signal,
    });
  } catch (cause) {
    if (cause?.name === "AbortError") throw apiError("Request timed out", { code: "timeout" });
    throw apiError("Network error: failed to fetch", { code: "network" });
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = `Server error (${res.status})`;
    try {
      const payload = await res.json();
      detail = extractDetailMessage(payload?.detail) || detail;
    } catch {
      // Non-JSON error page (e.g. a proxy's 502 HTML) — keep the status-based message.
    }
    const err = apiError(detail, { status: res.status, code: res.headers.get("X-Error-Code") || undefined });
    if (res.status === 401 && !AUTH_401_EXEMPT.some((p) => path.startsWith(p))) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw err;
  }
  if (res.status === 204) return null;
  try {
    return await res.json();
  } catch {
    throw apiError(`Server error (${res.status}): invalid response`, { status: 502, code: "bad_response" });
  }
}

/* ---------- response normalizers: the UI can rely on these shapes ---------- */

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const obj = (v) => (isObj(v) ? v : {});
const arr = (v) => (Array.isArray(v) ? v : []);
const objArr = (v) => arr(v).filter(isObj);

function page(res, mapItem = (x) => x) {
  const r = obj(res);
  const items = objArr(r.items).filter((it) => Number.isFinite(it.id)).map(mapItem);
  const total = Number.isFinite(r.total) ? r.total : items.length;
  return { ...r, items, total };
}

function aiResult(res) {
  const r = obj(res);
  const data = isObj(r.data) ? r.data : null;
  return { ...r, success: Boolean(r.success) && data !== null, data, is_mock: Boolean(r.is_mock) };
}

function withArrays(res, keys) {
  const r = { ...obj(res) };
  keys.forEach((k) => { r[k] = objArr(r[k]); });
  return r;
}

function chartPoints(res) {
  const r = obj(res);
  const prices = arr(r.prices)
    .filter((p) => Array.isArray(p) && p[0] !== null && p[1] !== null)
    .map((p) => [Number(p[0]), Number(p[1])])
    .filter(([ts, price]) => Number.isFinite(ts) && Number.isFinite(price) && price > 0);
  return { ...r, prices, is_mock: Boolean(r.is_mock) };
}

function accuracy(res) {
  const r = obj(res);
  const nums = (v) => arr(v).filter((x) => Number.isFinite(x));
  return { ...r, predicted_prices: nums(r.predicted_prices), actual_prices: nums(r.actual_prices), time_labels: arr(r.time_labels) };
}

function leaderboard(res) {
  const r = obj(res);
  const challenge = obj(r.challenge);
  return { ...r, providers: objArr(r.providers).filter((p) => typeof p.provider === "string"), challenge: { you: obj(challenge.you), everyone: obj(challenge.everyone) } };
}

function votePercentages(res) {
  const r = obj(res);
  const num = (v) => (Number.isFinite(v) ? v : 0);
  return { Bullish: num(r.Bullish), Neutral: num(r.Neutral), Bearish: num(r.Bearish), total_votes: num(r.total_votes) };
}

function fearGreed(res) {
  const r = obj(res);
  const d = obj(r.data);
  const valid = Number.isFinite(Number(d.value));
  return { ...r, data: valid ? { ...d, value: Math.min(100, Math.max(0, Math.round(Number(d.value)))) } : null, is_mock: Boolean(r.is_mock) };
}

export const api = {
  register: (username, password, email, captcha_token) => request("/auth/register", { method: "POST", body: { username, password, email, captcha_token } }),
  login: (username, password, totp_code) => request("/auth/login", { method: "POST", body: { username, password, totp_code } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me").then(obj),
  forgotPassword: (email, captcha_token) => request("/auth/forgot-password", { method: "POST", body: { email, captcha_token } }),
  verifyEmail: (code) => request("/auth/verify-email", { method: "POST", body: { code } }),
  resendVerification: () => request("/auth/resend-verification", { method: "POST" }),
  verifyResetCode: (email, code) => request("/auth/verify-reset-code", { method: "POST", body: { email, code } }),
  resetPassword: (email, code, new_password) => request("/auth/reset-password", { method: "POST", body: { email, code, new_password } }),

  listApiKeys: () => request("/account/api-keys").then(objArr),
  saveApiKey: (provider, api_key, extra = {}) => request("/account/api-keys", { method: "PUT", body: { provider, api_key, ...extra } }),
  deleteApiKey: (provider) => request(`/account/api-keys/${encodeURIComponent(provider)}`, { method: "DELETE" }),
  apiKeyLinks: () => request("/account/api-keys/links").then(obj),
  testApiKey: (provider) => request(`/account/api-keys/${encodeURIComponent(provider)}/test`, { method: "POST", timeoutMs: AI_TIMEOUT_MS }).then(obj),
  changePassword: (current_password, new_password) =>
    request("/account/change-password", { method: "POST", body: { current_password, new_password } }),
  logoutAllDevices: () => request("/account/logout-all-devices", { method: "POST" }),
  deleteAccount: (password) => request("/account/delete", { method: "POST", body: { password } }),
  totpSetup: () => request("/account/2fa/setup", { method: "POST" }),
  totpEnable: (code) => request("/account/2fa/enable", { method: "POST", body: { code } }),
  totpDisable: (password, code) => request("/account/2fa/disable", { method: "POST", body: { password, code } }),
  updateEmail: (email) => request("/account/email", { method: "PUT", body: { email } }),

  generateForecast: (provider, coin, horizon) =>
    request("/forecast", { method: "POST", body: { provider, coin, horizon, lang: currentLang() }, timeoutMs: AI_TIMEOUT_MS }).then(aiResult),
  estimateForecastCost: (provider, coin, horizon) =>
    request("/forecast/estimate-cost", { method: "POST", body: { provider, coin, horizon, lang: currentLang() } }),
  saveForecast: (provider, coin, horizon, forecast_data, is_mock) =>
    request("/forecast/save", { method: "POST", body: { provider, coin, horizon, forecast_data, is_mock } }),
  deleteForecast: (id) => request(`/forecast/history/${id}`, { method: "DELETE" }),
  forecastHistory: (symbol, daysBack = null, pageNo = 1, pageSize = 20) =>
    request(`/forecast/history?page=${pageNo}&page_size=${pageSize}${daysBack ? `&days_back=${daysBack}` : ""}${symbol ? `&symbol=${encodeURIComponent(symbol)}` : ""}`)
      .then((r) => page(r, (it) => ({ ...it, forecast_data: obj(it.forecast_data) }))),
  forecastAccuracy: (id) => request(`/forecast/history/${id}/accuracy`).then(accuracy),
  forecastLeaderboard: () => request("/forecast/leaderboard").then(leaderboard),
  bulkDeleteForecasts: (ids) => request("/forecast/history/bulk-delete", { method: "POST", body: { ids } }),
  bulkDeletePortfolio: (ids) => request("/portfolio/history/bulk-delete", { method: "POST", body: { ids } }),
  onchain: () => request("/market/onchain").then((r) => ({ items: objArr(obj(r).items).filter((it) => typeof it.coin === "string") })),
  submitTip: (id, price) => request(`/forecast/history/${id}/tip`, { method: "POST", body: { price } }),

  analyzePortfolio: (provider, holdings) =>
    request("/portfolio/analyze", { method: "POST", body: { provider, holdings, lang: currentLang() }, timeoutMs: AI_TIMEOUT_MS }).then(aiResult),
  estimatePortfolioCost: (provider, holdings) =>
    request("/portfolio/estimate-cost", { method: "POST", body: { provider, holdings, lang: currentLang() } }),
  savePortfolio: (provider, holdings, analysis_data, is_mock) =>
    request("/portfolio/save", { method: "POST", body: { provider, holdings, analysis_data, is_mock } }),
  deletePortfolioAnalysis: (id) => request(`/portfolio/history/${id}`, { method: "DELETE" }),
  portfolioHistory: (pageNo = 1, pageSize = 20) => request(`/portfolio/history?page=${pageNo}&page_size=${pageSize}`)
    .then((r) => page(r, (it) => ({ ...it, holdings: objArr(it.holdings), analysis_data: obj(it.analysis_data) }))),

  fearGreed: (refresh = false) => request(`/market/fear-greed${refresh ? "?refresh=true" : ""}`).then(fearGreed),
  headlines: () => request("/market/headlines").then((r) => withArrays(r, ["headlines"])),
  newsSentiment: (provider, titles) => request("/market/news-sentiment", { method: "POST", body: { provider, titles, lang: currentLang() }, timeoutMs: AI_TIMEOUT_MS }).then(aiResult),
  events: () => request(`/market/events?lang=${currentLang()}`).then((r) => withArrays(r, ["events"])),
  vote: (sentiment_vote) => request("/market/vote", { method: "POST", body: { sentiment_vote } }),
  myVote: () => request("/market/vote/mine").then(obj),
  votePercentages: () => request("/market/vote/percentages").then(votePercentages),
  livePrices: (ids, vsCurrency = "usd") =>
    request(`/market/prices?ids=${encodeURIComponent(ids.join(","))}&vs_currency=${vsCurrency}`).then((r) => ({ ...obj(r), prices: obj(obj(r).prices) })),
  marketChart: (coinId, vsCurrency = "usd", days = "7") =>
    request(`/market/chart?coin_id=${encodeURIComponent(coinId)}&vs_currency=${vsCurrency}&days=${days}`).then(chartPoints),
  searchCoins: (q) => request(`/market/coins/search?q=${encodeURIComponent(q)}`).then((r) => withArrays(r, ["results"])),
  dailyDigest: (provider) => request("/market/daily-digest", { method: "POST", body: { provider, lang: currentLang() }, timeoutMs: AI_TIMEOUT_MS }).then(aiResult),

  sendChatMessage: (provider, messages) => request("/chat", { method: "POST", body: { provider, messages, lang: currentLang() }, timeoutMs: AI_TIMEOUT_MS }).then(aiResult),
};
