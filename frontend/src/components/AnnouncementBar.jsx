/** Site-wide message set by the admin; each message can be dismissed once. */

import { X } from "lucide-react";
import { useState } from "react";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";

const KEY = "aca_dismissed_announcement";

function dismissed() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}

export default function AnnouncementBar() {
  const { announcement, announcement_level: level } = useAppConfig();
  const { t } = useLanguage();
  const [hidden, setHidden] = useState(dismissed);
  if (!announcement || hidden === announcement) return null;
  const close = () => {
    try { localStorage.setItem(KEY, announcement); } catch { /* best-effort */ }
    setHidden(announcement);
  };
  return (
    <div className={`announcement announcement-${level}`} role="status">
      <span>{announcement}</span>
      <button type="button" onClick={close} aria-label={t("common.close")}><X size={14} /></button>
    </div>
  );
}
