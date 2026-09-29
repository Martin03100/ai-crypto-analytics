/** Translation lookup. */

import en from "./locales/en.json";
import sk from "./locales/sk.json";
import cz from "./locales/cz.json";

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "sk", label: "Slovenčina" },
  { code: "cs", label: "Čeština" },
];

const DICTS = { en, sk, cs: cz };
export const DEFAULT_LANG = "en";

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
