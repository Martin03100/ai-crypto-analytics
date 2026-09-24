/**
 * api.js
 * =======
 * Tenky fetch wrapper pre FastAPI backend. Autentifikacia bezi cez
 * HttpOnly cookie (nastavenu backendom pri /auth/login|/register), takze
 * kazdy request posiela `credentials: "include"` a ZIADNY token sa uz
 * neuklada ani necita z localStorage (ochrana proti XSS kradezi tokenu).
 *
 * CSRF: backend pouziva "double-submit cookie" - kazdy mutacny request
 * (POST/PUT/DELETE) musi zopakovat hodnotu JS-citatelnej `aca_csrf` cookie
 * v hlavicke X-CSRF-Token. Cudzia stranka nasu cookie precitat nevie
 * (same-origin policy), takze bez tejto hlavicky backend request odmietne.
 */

 const BASE = "/api";
 const CSRF_COOKIE_NAME = "aca_csrf";
 const LANG_STORAGE_KEY = "aca_lang";
 const VALID_LANGS = ["en", "sk", "cs"];
 
 /** Cita aktualne zvoleny jazyk UI priamo z localStorage (rovnaky kluc ako
  * LanguageContext), aby ho mohli AI endpointy (forecast/portfolio/news/
  * digest/chat/events) poslat backendu - ten ho pouziva na lokalizaciu
  * DEMO/MOCK obsahu (viď app/i18n_content.py). Skutocny text z AI providera
  * sa nou neriadi - ten je vzdy v jazyku promptu. */
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
 
 /**
  * FastAPI's `detail` field isn't always a plain string: Pydantic validation
  * errors (HTTP 422) return an ARRAY of `{loc, msg, type}` objects. Without
  * this, `new Error(detail)` used to stringify that array as "[object
  * Object]" and show it straight to the user. Here we always reduce `detail`
  * down to a single readable string before it reaches humanizeError().
  */
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
       // ignore parse error (e.g. empty body, non-JSON response)
     }
     const err = new Error(detail);
     err.status = res.status;
     throw err;
   }
   if (res.status === 204) return null;
   return res.json();
 }
 
 export const api = {
   register: (username, password, email) => request("/auth/register", { method: "POST", body: { username, password, email } }),
   login: (username, password) => request("/auth/login", { method: "POST", body: { username, password } }),
   logout: () => request("/auth/logout", { method: "POST" }),
   me: () => request("/auth/me"),
   forgotPassword: (username) => request("/auth/forgot-password", { method: "POST", body: { username } }),
   resetPassword: (token, new_password) => request("/auth/reset-password", { method: "POST", body: { token, new_password } }),
 
   listApiKeys: () => request("/account/api-keys"),
   saveApiKey: (provider, api_key) => request("/account/api-keys", { method: "PUT", body: { provider, api_key } }),
   deleteApiKey: (provider) => request(`/account/api-keys/${provider}`, { method: "DELETE" }),
   apiKeyLinks: () => request("/account/api-keys/links"),
   testApiKey: (provider) => request(`/account/api-keys/${provider}/test`, { method: "POST" }),
   changePassword: (current_password, new_password) =>
     request("/account/change-password", { method: "POST", body: { current_password, new_password } }),
   logoutAllDevices: () => request("/account/logout-all-devices", { method: "POST" }),
   updateEmail: (email) => request("/account/email", { method: "PUT", body: { email } }),
 
   generateForecast: (provider, coin, horizon) =>
     request("/forecast", { method: "POST", body: { provider, coin, horizon, lang: currentLang() } }),
   saveForecast: (provider, coin, horizon, forecast_data, is_mock) =>
     request("/forecast/save", { method: "POST", body: { provider, coin, horizon, forecast_data, is_mock } }),
   deleteForecast: (id) => request(`/forecast/history/${id}`, { method: "DELETE" }),
   forecastHistory: (symbol, daysBack = 30, page = 1, pageSize = 20) =>
     request(`/forecast/history?days_back=${daysBack}&page=${page}&page_size=${pageSize}${symbol ? `&symbol=${symbol}` : ""}`),
 
   analyzePortfolio: (provider, holdings) =>
     request("/portfolio/analyze", { method: "POST", body: { provider, holdings, lang: currentLang() } }),
   savePortfolio: (provider, holdings, analysis_data, is_mock) =>
     request("/portfolio/save", { method: "POST", body: { provider, holdings, analysis_data, is_mock } }),
   deletePortfolioAnalysis: (id) => request(`/portfolio/history/${id}`, { method: "DELETE" }),
   portfolioHistory: (page = 1, pageSize = 20) => request(`/portfolio/history?page=${page}&page_size=${pageSize}`),
 
   fearGreed: () => request("/market/fear-greed"),
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
 