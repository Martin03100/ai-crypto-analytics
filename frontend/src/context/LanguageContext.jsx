import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translate } from "../i18n/translations";

const LanguageContext = createContext(null);
const STORAGE_KEY = "aca_lang";
const VALID = ["sk", "cs", "en"];
// Predvolený jazyk pri úplne prvom otvorení aplikácie (žiadna hodnota
// v localStorage) je vždy angličtina, bez ohľadu na jazyk prehliadača.
const DEFAULT_LANG = "en";

function loadLang() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return VALID.includes(stored) ? stored : DEFAULT_LANG;
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(loadLang);

  // Drží <html lang="..."> v súlade so zvoleným jazykom (accessibilita,
  // správne vykresľovanie/SEO) a zároveň zaisťuje, že aj celkom prvá
  // návšteva (bez uloženej hodnoty) uloží explicitný default do localStorage.
  useEffect(() => {
    document.documentElement.setAttribute("lang", lang);
    if (!localStorage.getItem(STORAGE_KEY)) {
      localStorage.setItem(STORAGE_KEY, DEFAULT_LANG);
    }
  }, [lang]);

  const setLang = useCallback((next) => {
    if (!VALID.includes(next)) return;
    localStorage.setItem(STORAGE_KEY, next);
    setLangState(next);
  }, []);

  const t = useCallback((key, params) => translate(key, lang, params), [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage musi byt pouzity vnutri LanguageProvider");
  return ctx;
}
