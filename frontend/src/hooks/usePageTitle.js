import { useEffect } from "react";
import { useLanguage } from "../context/LanguageContext";

/**
 * Nastavi document.title na preklad `titleKey` + " — AI Crypto Analytics".
 * Bez tohto by mala kazda stranka appky rovnaky staticky titulok z
 * index.html — zle pre historiu prehliadaca, taby aj pouzivatelov
 * screen readerov, ktori titulok stranky pocuju pri kazdej navigacii.
 */
export function usePageTitle(titleKey) {
  const { t, lang } = useLanguage();
  useEffect(() => {
    document.title = `${t(titleKey)} — AI Crypto Analytics`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleKey, lang]);
}

export default usePageTitle;
