/** Vitest: load every app language up front (the app loads them on demand). */

import { loadLanguage } from "./i18n/translations";

await Promise.all(["sk", "cs", "de", "pl"].map(loadLanguage));
