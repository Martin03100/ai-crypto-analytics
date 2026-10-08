/** Language context. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { isLanguageLoaded, loadLanguage, translate } from "../i18n/translations";

const LanguageContext = createContext(null);
const STORAGE_KEY = "aca_lang";
const VALID = ["sk", "cs", "de", "pl", "en"];
const DEFAULT_LANG = "en";

function readStored() {
  try { return localStorage.getItem(STORAGE_KEY); } catch { return null; }
}

function writeStored(value) {
  try { localStorage.setItem(STORAGE_KEY, value); } catch { /* storage blocked: the choice lasts this session */ }
}

/** First visit: follow the browser language (Slovak, Czech, German and Polish users get their language right away). */
export function detectLang(languages = typeof navigator === "undefined" ? [] : navigator.languages || [navigator.language]) {
  for (const tag of languages) {
    const base = String(tag || "").toLowerCase().split("-")[0];
    if (VALID.includes(base)) return base;
  }
  return DEFAULT_LANG;
}

export function initialLang() {
  return loadLang();
}

function loadLang() {
  const stored = readStored();
  return VALID.includes(stored) ? stored : detectLang();
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(loadLang);

  useEffect(() => {
    document.documentElement.setAttribute("lang", lang);
    if (!readStored()) writeStored(lang);
  }, [lang]);

  const setLang = useCallback((next) => {
    if (!VALID.includes(next)) return;
    writeStored(next);
    if (isLanguageLoaded(next)) setLangState(next);
    else loadLanguage(next).then(() => setLangState(next));
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
