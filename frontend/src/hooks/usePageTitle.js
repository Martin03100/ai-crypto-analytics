/** Page title hook. */

import { useEffect } from "react";
import { useLanguage } from "../context/LanguageContext";

export function usePageTitle(titleKey) {
  const { t, lang } = useLanguage();
  useEffect(() => {
    document.title = `${t(titleKey)} — AI Crypto Analytics`;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleKey, lang]);
}

export default usePageTitle;
