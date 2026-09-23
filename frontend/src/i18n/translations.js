/**
 * translations.js
 * =================
 * Načítava prekladové slovníky z ./locales/{en,sk,cz}.json a poskytuje
 * `translate(key, lang, params)` s podporou interpolácie premenných
 * (`{meno}` v šablóne sa nahradí hodnotou z `params.meno`).
 *
 * Samotný text AI analýz/predikcií sa NEPREKLADÁ — ten prichádza priamo
 * z AI providera v jazyku promptu (viď app/services/validators.py).
 */
import en from "./locales/en.json";
import sk from "./locales/sk.json";
import cz from "./locales/cz.json";

// Interný kód pre češtinu zostáva "cs" (ISO 639-1), súbor sa volá cz.json
// kvôli čitateľnosti/konzistencii s SK a EN skratkami v UI.
export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "sk", label: "Slovenčina" },
  { code: "cs", label: "Čeština" },
];

const DICTS = { en, sk, cs: cz };
export const DEFAULT_LANG = "en";

/** Nahradí `{kluc}` v šablóne hodnotami z `params`. Chýbajúci parameter sa
 * ponechá ako-je (nespôsobí pád), aby sa dala chyba ľahko odhaliť vo vývoji. */
function interpolate(template, params) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name) => (
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
  ));
}

/** Preloží `key` do jazyka `lang`. Fallback: lang -> en -> samotny kluc
 * (nikdy nezobrazi undefined, aj chybajuci preklad je viditelny ako kluc). */
export function translate(key, lang, params) {
  const dict = DICTS[lang] || DICTS[DEFAULT_LANG];
  const template = dict[key] ?? DICTS[DEFAULT_LANG][key] ?? key;
  return interpolate(template, params);
}

export default translate;
