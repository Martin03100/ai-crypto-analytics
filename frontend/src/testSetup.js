/** Vitest: load every app language up front (the app loads them on demand) and use one time zone everywhere. */

import { loadLanguage } from "./i18n/translations";

// Calendar helpers count days in the viewer's time zone; tests pin it, so they pass on any machine (CI runs in UTC,
// a developer in Prague does not).
process.env.TZ = "UTC";

await Promise.all(["sk", "cs", "de", "pl"].map(loadLanguage));
