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

// Counted texts ("1 deň", "2 dni", "5 dní") have variants "key#one", "#few", "#many" and "#other"; the count is the
// first of these params that is a number.
const PLURAL_PARAMS = ["count", "n", "total", "days"];
const pluralRules = {};

function pluralKey(key, lang, params, dict) {
  if (!params || dict[`${key}#other`] === undefined) return key;
  const name = PLURAL_PARAMS.find((p) => typeof params[p] === "number");
  if (!name) return key;
  const code = DICTS[lang] ? lang : DEFAULT_LANG;
  pluralRules[code] ||= new Intl.PluralRules(code);
  const variant = `${key}#${pluralRules[code].select(params[name])}`;
  return dict[variant] !== undefined ? variant : `${key}#other`;
}

export function translate(key, lang, params) {
  const dict = DICTS[lang] || DICTS[DEFAULT_LANG];
  const resolved = pluralKey(key, lang, params, dict);
  const template = dict[resolved] ?? DICTS[DEFAULT_LANG][resolved] ?? dict[key] ?? DICTS[DEFAULT_LANG][key] ?? key;
  return interpolate(template, params);
}

export default translate;
