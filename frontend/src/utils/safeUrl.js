/** URL sanitizer. */

export function safeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(String(value), window.location.origin);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch {
    return "";
  }
}

export default safeUrl;
