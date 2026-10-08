/** Translation lookup. */

import en from "./locales/en.json";

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "sk", label: "Slovenčina" },
  { code: "cs", label: "Čeština" },
  { code: "de", label: "Deutsch" },
  { code: "pl", label: "Polski" },
];

// English ships with the app; other languages are separate files loaded when first needed (keeps the first load small).
const DICTS = { en };
const LOADERS = {
  sk: () => import("./locales/sk.json"),
  cs: () => import("./locales/cz.json"),
  de: () => import("./locales/de.json"),
  pl: () => import("./locales/pl.json"),
};
export const DEFAULT_LANG = "en";

export function isLanguageLoaded(lang) {
  return Boolean(DICTS[lang]) || !LOADERS[lang];
}

/** Load a language's texts (no-op for English, unknown codes or one already loaded). Never rejects. */
export async function loadLanguage(lang) {
  if (isLanguageLoaded(lang)) return;
  try {
    DICTS[lang] = (await LOADERS[lang]()).default;
  } catch {
    /* offline and not cached: the app stays in English until it can load */
  }
}

function interpolate(template, params) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) => (
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
  ));
}

export function translate(key, lang, params) {
  const dict = DICTS[lang] || DICTS[DEFAULT_LANG];
  const template = dict[key] ?? DICTS[DEFAULT_LANG][key] ?? key;
  return interpolate(template, params);
}

export default translate;
