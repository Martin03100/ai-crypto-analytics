/** Shown in place of a Premium feature for users on the free plan. */

import { Crown } from "lucide-react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";

export default function PremiumGate({ title, text }) {
  const { t } = useLanguage();
  return (
    <div className="premium-gate">
      <div className="premium-gate-icon"><Crown size={18} /></div>
      <strong>{title}</strong>
      <p className="text-sub">{text}</p>
      <Link to="/premium" className="btn btn-primary btn-sm">{t("gate.cta")}</Link>
    </div>
  );
}
