import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { useLanguage } from "../context/LanguageContext";

/**
 * Zobrazi selectbox obmedzeny len na providerov, ktorych ma pouzivatel
 * pripojenych v Account Settings. Ak nema ziadneho, zobrazi banner
 * s odkazom na pripojenie namiesto selectboxu.
 */
export default function ProviderSelect({ providers, value, onChange, label }) {
  const { t } = useLanguage();
  const connected = providers.filter((p) => p.connected);
  const fieldLabel = label || t("provider.defaultLabel");

  if (connected.length === 0) {
    return (
      <div className="alert alert-warn" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <AlertTriangle size={16} />
        <span>
          {t("provider.connectPrompt")} <Link to="/account" style={{ color: "var(--amber)", fontWeight: 600 }}>{t("provider.connectLinkLabel")}</Link> {t("provider.connectSuffix")}
        </span>
      </div>
    );
  }

  return (
    <div className="field">
      <label>{fieldLabel}</label>
      <select className="select" value={value || ""} onChange={(e) => onChange(e.target.value)}>
        {connected.map((p) => (
          <option key={p.provider} value={p.provider}>{p.provider === "custom" ? t("provider.customLabel") : p.label}</option>
        ))}
      </select>
    </div>
  );
}
