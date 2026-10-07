/** Shown while the backend takes long to answer: on the free hosting plan the first request wakes the server up. */

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { SLOW_SERVER_EVENT } from "../api";
import { useLanguage } from "../context/LanguageContext";

export default function WakeBanner() {
  const { t } = useLanguage();
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const onSlow = (e) => setSlow(Boolean(e.detail?.slow));
    window.addEventListener(SLOW_SERVER_EVENT, onSlow);
    return () => window.removeEventListener(SLOW_SERVER_EVENT, onSlow);
  }, []);
  if (!slow) return null;
  return (
    <div className="wake-banner" role="status" aria-live="polite">
      <Loader2 size={14} className="spin" /> {t("wake.text")}
    </div>
  );
}
