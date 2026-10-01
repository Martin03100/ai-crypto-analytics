/** Service worker registration and offline-data housekeeping. */

export const API_CACHE = "api-data";
export const PWA_UPDATE_EVENT = "aca:pwa-update";
export const PWA_INSTALLABLE_EVENT = "aca:pwa-installable";

let applyUpdate = null;
let installPrompt = null;

export function initPwa() {
  // Chrome/Edge/Android fire this once, early; keep it so Settings can offer "Install" later.
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    installPrompt = e;
    window.dispatchEvent(new Event(PWA_INSTALLABLE_EVENT));
  });
  window.addEventListener("appinstalled", () => { installPrompt = null; });
  if (!("serviceWorker" in navigator) || import.meta.env.DEV) return;
  // Loaded lazily: the virtual module exists only in Vite builds, and the app shell should paint first.
  import("virtual:pwa-register").then(({ registerSW }) => {
    applyUpdate = registerSW({
      onNeedRefresh() {
        window.dispatchEvent(new Event(PWA_UPDATE_EVENT));
      },
    });
  }).catch(() => {});
}

/** Activate the waiting service worker and reload into the new version. */
export function updateApp() {
  applyUpdate?.(true);
}

// Offline session: who was signed in when the server last confirmed the session, and until when the app may
// keep showing that account's cached data without being able to reach the server again.
const OFFLINE_SESSION_KEY = "aca_offline_session";
export const OFFLINE_SESSION_MS = 24 * 3600 * 1000;

export function rememberOfflineSession(user, now = Date.now()) {
  try {
    localStorage.setItem(OFFLINE_SESSION_KEY, JSON.stringify({ user, until: now + OFFLINE_SESSION_MS }));
  } catch { /* storage blocked: no offline start */ }
}

/** The remembered user if still within the offline window; otherwise null (and the record is dropped). */
export function offlineSessionUser(now = Date.now()) {
  try {
    const saved = JSON.parse(localStorage.getItem(OFFLINE_SESSION_KEY) || "null");
    if (saved?.user && Number(saved.until) > now) return saved.user;
    localStorage.removeItem(OFFLINE_SESSION_KEY);
  } catch { /* unreadable: treat as none */ }
  return null;
}

function forgetOfflineSession() {
  try { localStorage.removeItem(OFFLINE_SESSION_KEY); } catch { /* nothing stored */ }
}

/** Drop cached API responses (they belong to the signed-in user). Called on sign-out and session expiry. */
export async function clearOfflineData() {
  forgetOfflineSession();
  try {
    if ("caches" in window) await caches.delete(API_CACHE);
  } catch {
    // Cache storage unavailable (private mode): nothing was stored.
  }
}

export function isStandalone() {
  return window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

/** iPhone/iPad Safari has no install prompt; the user adds the app via Share -> Add to Home Screen. */
export function isIosSafari() {
  const ua = window.navigator.userAgent;
  return /iPad|iPhone|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
}

export function canPromptInstall() {
  return installPrompt !== null;
}

export async function promptInstall() {
  if (!installPrompt) return false;
  const prompt = installPrompt;
  installPrompt = null;
  await prompt.prompt();
  const { outcome } = await prompt.userChoice;
  return outcome === "accepted";
}
