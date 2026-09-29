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

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (method !== "GET") {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `Server error (${res.status})`;
    try {
      const payload = await res.json();
      detail = extractDetailMessage(payload.detail) || detail;
    } catch {
    }
    const err = new Error(detail);
    err.status = res.status;
    err.code = res.headers.get("X-Error-Code") || undefined;
    if (res.status === 401 && !AUTH_401_EXEMPT.some((p) => path.startsWith(p))) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  register: (username, password, email, captcha_token) => request("/auth/register", { method: "POST", body: { username, password, email, captcha_token } }),
  login: (username, password, totp_code) => request("/auth/login", { method: "POST", body: { username, password, totp_code } }),
  logout: () => request("/auth/logout", { method: "POST" }),
  me: () => request("/auth/me"),
  forgotPassword: (email, captcha_token) => request("/auth/forgot-password", { method: "POST", body: { email, captcha_token } }),
  verifyEmail: (code) => request("/auth/verify-email", { method: "POST", body: { code } }),
  resendVerification: () => request("/auth/resend-verification", { method: "POST" }),
  verifyResetCode: (email, code) => request("/auth/verify-reset-code", { method: "POST", body: { email, code } }),
  resetPassword: (email, code, new_password) => request("/auth/reset-password", { method: "POST", body: { email, code, new_password } }),

  listApiKeys: () => request("/account/api-keys"),
  saveApiKey: (provider, api_key, extra = {}) => request("/account/api-keys", { method: "PUT", body: { provider, api_key, ...extra } }),
  deleteApiKey: (provider) => request(`/account/api-keys/${provider}`, { method: "DELETE" }),
  apiKeyLinks: () => request("/account/api-keys/links"),
  testApiKey: (provider) => request(`/account/api-keys/${provider}/test`, { method: "POST" }),
  changePassword: (current_password, new_password) =>
    request("/account/change-password", { method: "POST", body: { current_password, new_password } }),
  logoutAllDevices: () => request("/account/logout-all-devices", { method: "POST" }),
  deleteAccount: (password) => request("/account/delete", { method: "POST", body: { password } }),
  totpSetup: () => request("/account/2fa/setup", { method: "POST" }),
  totpEnable: (code) => request("/account/2fa/enable", { method: "POST", body: { code } }),
  totpDisable: (password, code) => request("/account/2fa/disable", { method: "POST", body: { password, code } }),
  updateEmail: (email) => request("/account/email", { method: "PUT", body: { email } }),

  generateForecast: (provider, coin, horizon) =>
    request("/forecast", { method: "POST", body: { provider, coin, horizon, lang: currentLang() } }),
  estimateForecastCost: (provider, coin, horizon) =>
    request("/forecast/estimate-cost", { method: "POST", body: { provider, coin, horizon, lang: currentLang() } }),
  saveForecast: (provider, coin, horizon, forecast_data, is_mock) =>
    request("/forecast/save", { method: "POST", body: { provider, coin, horizon, forecast_data, is_mock } }),
  deleteForecast: (id) => request(`/forecast/history/${id}`, { method: "DELETE" }),
  forecastHistory: (symbol, daysBack = 30, page = 1, pageSize = 20) =>
    request(`/forecast/history?days_back=${daysBack}&page=${page}&page_size=${pageSize}${symbol ? `&symbol=${encodeURIComponent(symbol)}` : ""}`),
  forecastAccuracy: (id) => request(`/forecast/history/${id}/accuracy`),
  forecastLeaderboard: () => request("/forecast/leaderboard"),
  bulkDeleteForecasts: (ids) => request("/forecast/history/bulk-delete", { method: "POST", body: { ids } }),
  bulkDeletePortfolio: (ids) => request("/portfolio/history/bulk-delete", { method: "POST", body: { ids } }),
  onchain: () => request("/market/onchain"),
  submitTip: (id, price) => request(`/forecast/history/${id}/tip`, { method: "POST", body: { price } }),

  analyzePortfolio: (provider, holdings) =>
    request("/portfolio/analyze", { method: "POST", body: { provider, holdings, lang: currentLang() } }),
  estimatePortfolioCost: (provider, holdings) =>
    request("/portfolio/estimate-cost", { method: "POST", body: { provider, holdings, lang: currentLang() } }),
  savePortfolio: (provider, holdings, analysis_data, is_mock) =>
    request("/portfolio/save", { method: "POST", body: { provider, holdings, analysis_data, is_mock } }),
  deletePortfolioAnalysis: (id) => request(`/portfolio/history/${id}`, { method: "DELETE" }),
  portfolioHistory: (page = 1, pageSize = 20) => request(`/portfolio/history?page=${page}&page_size=${pageSize}`),

  fearGreed: (refresh = false) => request(`/market/fear-greed${refresh ? "?refresh=true" : ""}`),
  headlines: () => request("/market/headlines"),
  newsSentiment: (provider, titles) => request("/market/news-sentiment", { method: "POST", body: { provider, titles, lang: currentLang() } }),
  events: () => request(`/market/events?lang=${currentLang()}`),
  vote: (sentiment_vote) => request("/market/vote", { method: "POST", body: { sentiment_vote } }),
  myVote: () => request("/market/vote/mine"),
  votePercentages: () => request("/market/vote/percentages"),
  livePrices: (ids, vsCurrency = "usd") =>
    request(`/market/prices?ids=${encodeURIComponent(ids.join(","))}&vs_currency=${vsCurrency}`),
  marketChart: (coinId, vsCurrency = "usd", days = "7") =>
    request(`/market/chart?coin_id=${encodeURIComponent(coinId)}&vs_currency=${vsCurrency}&days=${days}`),
  searchCoins: (q) => request(`/market/coins/search?q=${encodeURIComponent(q)}`),
  dailyDigest: (provider) => request("/market/daily-digest", { method: "POST", body: { provider, lang: currentLang() } }),

  sendChatMessage: (provider, messages) => request("/chat", { method: "POST", body: { provider, messages, lang: currentLang() } }),
};
