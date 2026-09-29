// Provider errors carry the useful part (e.g. which quota was hit) at the end,
// so show the whole message; only guard against absurdly long payloads.
export const TECH_DETAIL_MAX_CHARS = 4000;
export function formatTechDetail(message) {
  // Some SDKs return escaped newlines ("\\n"); render them as real line breaks.
  const text = String(message).replace(/\\n/g, "\n");
  return text.length > TECH_DETAIL_MAX_CHARS ? `${text.slice(0, TECH_DETAIL_MAX_CHARS)}…` : text;
}
