/** Locale helpers. */

const LOCALE_MAP = { en: "en-US", sk: "sk-SK", cs: "cs-CZ" };

export function localeForLang(lang) {
  return LOCALE_MAP[lang] || LOCALE_MAP.en;
}

export default localeForLang;
