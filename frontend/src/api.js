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
// AI calls run as background jobs on the server; the client polls until the model has finished.
export const AI_TIMEOUT_MS = 180_000;
const JOB_POLL_MS = 1_000;
const COLD_START_RETRY_MS = 2_000;

function apiError(message, extra = {}) {
  const err = new Error(message);
  Object.assign(err, extra);
  return err;
}

/**
 * A read that hits a gateway error (502-504) is retried once: on the free hosting plan the first request after a
 * pause only wakes the backend and the proxy gives up before it is ready; the second one then succeeds.
 */
async function request(path, options = {}) {
  try {
    return await requestOnce(path, options);
  } catch (err) {
    if ((options.method || "GET") !== "GET" || ![502, 503, 504].includes(err?.status)) throw err;
    await sleep(COLD_START_RETRY_MS);
    return requestOnce(path, options);
  }
}

async function requestOnce(path, { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS, extraHeaders } = {}) {
  const headers = { "Content-Type": "application/json", ...extraHeaders };
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

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** The server could not be reached or answered through the proxy with a gateway error (cold start, redeploy). */
export function isTransient(err) {
  return err?.code === "network" || err?.code === "timeout" || [502, 503, 504].includes(err?.status);
}

/**
 * Start an AI request as a background job and wait for its result. Each HTTP call stays short, so the
 * ~26 s limit of the hosting proxy no longer cuts off slow models. A server that answers inline still works.
 */
async function requestJob(path, options = {}) {
  const started = await request(path, { method: "POST", ...options, extraHeaders: { Prefer: "respond-async" } });
  if (!started || typeof started.job_id !== "string") return started;
  const deadline = Date.now() + AI_TIMEOUT_MS;
  let hiccups = 0;
  while (Date.now() < deadline) {
    await sleep(JOB_POLL_MS);
    try {
      const job = await request(`/jobs/${encodeURIComponent(started.job_id)}`);
      hiccups = 0;
      if (job?.status === "done") return job.result;
    } catch (err) {
      // A dropped connection or a proxy/backend blip (502-504) while polling is not a failure of the job itself.
      if (!isTransient(err) || ++hiccups > 5) throw err;
    }
  }
  throw apiError("Request timed out", { code: "timeout" });
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

function watchlist(res) {
  const r = obj(res);
  return { coins: arr(r.coins), available: arr(r.available), max: Number(r.max) || 12 };
}

export const api = {
  register: (username, password, email, captcha_token, referral_code) => request("/auth/register", {
    method: "POST", body: { username, password, email, captcha_token, lang: currentLang(), referral_code: referral_code || undefined },
  }),
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
  testApiKey: (provider) => requestJob(`/account/api-keys/${encodeURIComponent(provider)}/test`).then(obj),
  changePassword: (current_password, new_password) =>
    request("/account/change-password", { method: "POST", body: { current_password, new_password } }),
  logoutAllDevices: () => request("/account/logout-all-devices", { method: "POST" }),
  deleteAccount: (password) => request("/account/delete", { method: "POST", body: { password } }),
  totpSetup: () => request("/account/2fa/setup", { method: "POST" }),
  totpEnable: (code) => request("/account/2fa/enable", { method: "POST", body: { code } }),
  totpDisable: (password, code) => request("/account/2fa/disable", { method: "POST", body: { password, code } }),
  updateEmail: (email) => request("/account/email", { method: "PUT", body: { email } }),
  backtest: (coin, horizon) =>
    request(`/forecast/backtest?coin=${encodeURIComponent(coin)}&horizon=${encodeURIComponent(horizon)}`).then(obj),
  shareForecast: (id) => request(`/forecast/history/${id}/share`, { method: "POST" }).then(obj),
  unshareForecast: (id) => request(`/forecast/history/${id}/share`, { method: "DELETE" }),
  serviceStatus: () => request("/public/status").then((r) => withArrays(r, ["services"])),
  membership: () => request("/account/membership").then(obj),
  setNickname: (nickname) => request("/account/nickname", { method: "PUT", body: { nickname } }),
  setPreferences: (prefs) => request("/account/preferences", { method: "PUT", body: prefs }),
  notifications: () => request("/account/notifications").then((r) => withArrays(r, ["items"])),
  readNotifications: () => request("/account/notifications/read", { method: "POST" }),
  checkout: (consent) => request("/billing/checkout", { method: "POST", body: consent }),
  alerts: () => request("/alerts").then((r) => withArrays(r, ["items"])),
  createAlert: (coin, direction, target_price) => request("/alerts", { method: "POST", body: { coin, direction, target_price } }),
  deleteAlert: (id) => request(`/alerts/${encodeURIComponent(id)}`, { method: "DELETE" }),
  myStats: () => request("/account/stats").then((r) => withArrays(r, ["by_provider", "by_coin", "by_horizon"])),
  exportDataUrl: () => `${BASE}/account/export`,
  billingPortal: () => request("/billing/portal", { method: "POST" }),
  publicConfig: () => request("/public/config").then(obj),
  adminStats: () => request("/admin/stats").then(obj),
  adminUsers: (q, page) => request(`/admin/users?q=${encodeURIComponent(q || "")}&page=${page || 1}`).then((r) => withArrays(r, ["items"])),
  adminUpdateUser: (id, changes) => request(`/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body: changes }),
  adminWaitlist: () => request("/admin/waitlist").then((r) => withArrays(r, ["items"])),
  adminWaitlistCsvUrl: () => `${BASE}/admin/waitlist.csv`,
  adminSettings: () => request("/admin/settings").then(obj),
  adminSaveSettings: (values) => request("/admin/settings", { method: "PUT", body: { values } }),
  premiumInfo: () => request("/public/premium").then(obj),
  tipsters: (period) => request(`/public/tipsters?period=${period === "all" ? "all" : "week"}`).then((r) => withArrays(r, ["leaders"])),
  unsubscribeDigest: async (userId, token) => {
    if (!readCookie(CSRF_COOKIE_NAME)) await request("/health").catch(() => {});
    return request("/public/digest/unsubscribe", { method: "POST", body: { user_id: userId, token } });
  },
  trackRecord: () => request("/public/track-record").then((r) => withArrays(r, ["providers", "recent"])),
  joinWaitlist: async (email, lang, source) => {
    // A first-time visitor may not have the CSRF cookie yet; any API response sets it.
    if (!readCookie(CSRF_COOKIE_NAME)) await request("/health").catch(() => {});
    return request("/public/waitlist", { method: "POST", body: { email, lang, source: source || undefined } });
  },
  sharedForecast: (token) => request(`/public/forecasts/${encodeURIComponent(token)}`).then(obj),
  loadDemoData: () => request(`/account/demo-data?lang=${currentLang()}`, { method: "POST", timeoutMs: AI_TIMEOUT_MS }).then(obj),
  removeDemoData: () => request("/account/demo-data", { method: "DELETE" }).then(obj),
  accountActivity: () => request("/account/activity").then((r) => withArrays(r, ["events"])),

  generateForecast: (provider, coin, horizon) =>
    requestJob("/forecast", { body: { provider, coin, horizon, lang: currentLang() } }).then(aiResult),
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
    requestJob("/portfolio/analyze", { body: { provider, holdings, lang: currentLang() } }).then(aiResult),
  estimatePortfolioCost: (provider, holdings) =>
    request("/portfolio/estimate-cost", { method: "POST", body: { provider, holdings, lang: currentLang() } }),
  savePortfolio: (provider, holdings, analysis_data, is_mock) =>
    request("/portfolio/save", { method: "POST", body: { provider, holdings, analysis_data, is_mock } }),
  deletePortfolioAnalysis: (id) => request(`/portfolio/history/${id}`, { method: "DELETE" }),
  portfolioHistory: (pageNo = 1, pageSize = 20) => request(`/portfolio/history?page=${pageNo}&page_size=${pageSize}`)
    .then((r) => page(r, (it) => ({ ...it, holdings: objArr(it.holdings), analysis_data: obj(it.analysis_data) }))),

  fearGreed: (refresh = false) => request(`/market/fear-greed${refresh ? "?refresh=true" : ""}`).then(fearGreed),
  headlines: () => request("/market/headlines").then((r) => withArrays(r, ["headlines"])),
  newsSentiment: (provider, titles) => requestJob("/market/news-sentiment", { body: { provider, titles, lang: currentLang() } }).then(aiResult),
  events: () => request(`/market/events?lang=${currentLang()}`).then((r) => withArrays(r, ["events"])),
  vote: (sentiment_vote) => request("/market/vote", { method: "POST", body: { sentiment_vote } }),
  myVote: () => request("/market/vote/mine").then(obj),
  votePercentages: () => request("/market/vote/percentages").then(votePercentages),
  livePrices: (ids, vsCurrency = "usd") =>
    request(`/market/prices?ids=${encodeURIComponent(ids.join(","))}&vs_currency=${vsCurrency}`).then((r) => ({ ...obj(r), prices: obj(obj(r).prices) })),
  marketChart: (coinId, vsCurrency = "usd", days = "7") =>
    request(`/market/chart?coin_id=${encodeURIComponent(coinId)}&vs_currency=${vsCurrency}&days=${days}`).then(chartPoints),
  searchCoins: (q) => request(`/market/coins/search?q=${encodeURIComponent(q)}`).then((r) => withArrays(r, ["results"])),
  dailyDigest: (provider) => requestJob("/market/daily-digest", { body: { provider, lang: currentLang() } }).then(aiResult),

  watchlist: () => request("/account/watchlist").then(watchlist),
  setWatchlist: (coins) => request("/account/watchlist", { method: "PUT", body: { coins } }).then(watchlist),

  schedules: () => request("/schedules").then((r) => ({ items: objArr(obj(r).items), max: Number(obj(r).max) || 0 })),
  createSchedule: (schedule) => request("/schedules", { method: "POST", body: { ...schedule, lang: currentLang() } }).then(obj),
  setScheduleActive: (id, active) => request(`/schedules/${id}`, { method: "PATCH", body: { active } }).then(obj),
  deleteSchedule: (id) => request(`/schedules/${id}`, { method: "DELETE" }),
  historyCsvUrl: () => `${BASE}/forecast/history/export.csv`,

  sendChatMessage: (provider, messages) => requestJob("/chat", { body: { provider, messages, lang: currentLang() } }).then(aiResult),
};
