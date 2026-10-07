/** Remembers an invite code from a ?ref= link until the visitor signs up. */

const KEY = "aca_ref";
const CODE_RE = /^[A-Z0-9]{4,16}$/;

export function captureReferralCode(search = typeof window !== "undefined" ? window.location.search : "") {
  try {
    const code = (new URLSearchParams(search).get("ref") || "").trim().toUpperCase();
    if (CODE_RE.test(code)) localStorage.setItem(KEY, code);
  } catch {
    /* best-effort */
  }
}

export function getReferralCode() {
  try {
    const code = localStorage.getItem(KEY);
    return code && CODE_RE.test(code) ? code : null;
  } catch {
    return null;
  }
}
