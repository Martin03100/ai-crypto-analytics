/** Ambassador badge for people who invited friends: bronze (1), silver (5), gold (10). */

import { Medal } from "lucide-react";
import { useLanguage } from "../context/LanguageContext";

export default function AmbassadorBadge({ level, compact = false }) {
  const { t } = useLanguage();
  if (!["bronze", "silver", "gold"].includes(level)) return null;
  const label = t(`badge.${level}`);
  return (
    <span className={`ambassador ambassador-${level} ${compact ? "ambassador-compact" : ""}`} title={label} aria-label={label}>
      <Medal size={compact ? 11 : 13} />{!compact && <span>{label}</span>}
    </span>
  );
}
