// Optional error monitoring with Sentry, enabled only when VITE_SENTRY_DSN is set at build time.
// The SDK is loaded lazily, so the app bundle stays the same size when monitoring is off.

const SECRET_PATTERNS = [
  /(sk-|pplx-|AIza|xai-|gsk_)[A-Za-z0-9_-]{8,}/g,
  /(bearer\s+)[A-Za-z0-9._-]+/gi,
];

let sentry = null;
const queued = [];

export function scrubText(text) {
  return SECRET_PATTERNS.reduce((out, re) => out.replace(re, (_m, prefix) => `${prefix}[redacted]`), String(text ?? ""));
}

export function scrubEvent(event) {
  if (event?.request) {
    delete event.request.cookies;
    delete event.request.data;
    if (event.request.headers) delete event.request.headers.Cookie;
  }
  (event?.exception?.values || []).forEach((v) => { if (typeof v.value === "string") v.value = scrubText(v.value); });
  (event?.breadcrumbs || []).forEach((b) => { if (typeof b.message === "string") b.message = scrubText(b.message); });
  return event;
}

export function initMonitoring(dsn = import.meta.env.VITE_SENTRY_DSN) {
  if (!dsn) return Promise.resolve(false);
  return import("@sentry/react")
    .then((Sentry) => {
      Sentry.init({ dsn, environment: import.meta.env.MODE, sendDefaultPii: false, beforeSend: scrubEvent });
      sentry = Sentry;
      queued.splice(0).forEach(([err, ctx]) => Sentry.captureException(err, ctx));
      return true;
    })
    .catch(() => false); // monitoring must never break the app
}

export function reportError(error, context) {
  if (sentry) sentry.captureException(error, context);
  else if (import.meta.env.VITE_SENTRY_DSN && queued.length < 20) queued.push([error, context]);
}
