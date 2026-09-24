/**
 * locale.js
 * ==========
 * Mapuje jazyk aplikácie (en/sk/cs) na Intl locale string pre formátovanie
 * dátumov a čísel (`toLocaleString`, `toLocaleDateString`...). Predtým bolo
 * "sk-SK" natvrdo zapísané na desiatkach miest v UI bez ohľadu na zvolený
 * jazyk aplikácie — teraz nasleduje aktuálny jazyk z LanguageContext.
 */
 const LOCALE_MAP = { en: "en-US", sk: "sk-SK", cs: "cs-CZ" };

 export function localeForLang(lang) {
   return LOCALE_MAP[lang] || LOCALE_MAP.en;
 }
 
 export default localeForLang;
 