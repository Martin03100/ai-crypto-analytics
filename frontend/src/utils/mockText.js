/** Strips the "[SAMPLE DATA]"-style prefixes the backend adds to demo text; the UI shows a badge instead. */
const MOCK_TAG = /^\s*\[(?:SAMPLE DATA|MOCK|DUMMY|DEMO)\]\s*/i;

export function stripMockTag(text) {
  return typeof text === "string" ? text.replace(MOCK_TAG, "") : text;
}
