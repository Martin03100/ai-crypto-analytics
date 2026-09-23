import { CheckCircle2, ExternalLink, KeyRound, Loader2, Save, Shield, Trash2, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "../components/Card";
import { SkeletonLines } from "../components/Skeleton";
import { useAuth } from "../context/AuthContext";
import { useProviders } from "../context/ProvidersContext";
import { useToast } from "../context/ToastContext";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Account() {
  const { user } = useAuth();
  const { push } = useToast();
  const { t } = useLanguage();
  usePageTitle("account.title");
  const { providers: keys, loading: keysLoading, refresh } = useProviders();
  const [links, setLinks] = useState({});
  const [inputs, setInputs] = useState({});
  const [saving, setSaving] = useState(null);
  const [testing, setTesting] = useState(null);

  useEffect(() => {
    api.apiKeyLinks().then(setLinks).catch(() => {});
  }, []);

  async function saveKey(provider) {
    const value = inputs[provider];
    if (value === undefined) return;
    setSaving(provider);
    try {
      await api.saveApiKey(provider, value);
      refresh();
      setInputs((prev) => ({ ...prev, [provider]: "" }));
      push(t("account.keySaved"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSaving(null);
    }
  }

  async function removeKey(provider) {
    setSaving(provider);
    try {
      await api.deleteApiKey(provider);
      refresh();
      push(t("account.keyDeleted"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSaving(null);
    }
  }

  async function testKey(provider) {
    setTesting(provider);
    try {
      const res = await api.testApiKey(provider);
      // res.message prichadza z backendu (viz app/routers/account.py) — pri
      // neuspechu ho humanizujeme cez push(..., "error"), rovnako ako ine chyby.
      push(res.message, res.valid ? "success" : "error");
    } catch (err) {
      push(err, "error");
    } finally {
      setTesting(null);
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("account.title")}</h1>
          <p className="page-sub">{t("account.loggedInAs")} <strong>{user?.username}</strong></p>
        </div>
      </div>

      <Card title={t("account.aiSettingsTitle")} icon={KeyRound} style={{ marginBottom: 16 }}>
        <div className="alert alert-warn" style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 18 }}>
          <Shield size={16} style={{ marginTop: 1, flexShrink: 0 }} />
          <span>{t("account.securityNotice")}</span>
        </div>

        {keysLoading && keys.length === 0 && <SkeletonLines count={5} />}

        {keys.length > 0 && (
          <div className="provider-list">
            {keys.map((k) => (
              <div key={k.provider} className={`provider-row ${k.connected ? "connected" : ""}`}>
                <span className={`provider-status-dot ${k.connected ? "on" : "off"}`} />
                <div style={{ flex: "0 0 150px" }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{k.label}</div>
                  {k.connected && (
                    <div className="mono text-sub" style={{ marginTop: 2 }}>{k.masked_preview}</div>
                  )}
                  {links[k.provider] && (
                    <a href={links[k.provider]} target="_blank" rel="noreferrer" className="key-link" style={{ display: "inline-flex", alignItems: "center", gap: 3, marginTop: 3 }}>
                      {t("account.getKeyLink")} <ExternalLink size={10} />
                    </a>
                  )}
                </div>
                <input
                  className="input"
                  type="password"
                  placeholder={k.connected ? t("account.keyPlaceholderConnected") : t("account.keyPlaceholderNew")}
                  value={inputs[k.provider] ?? ""}
                  onChange={(e) => setInputs((prev) => ({ ...prev, [k.provider]: e.target.value }))}
                  style={{ flex: 1 }}
                />
                <div className="provider-row-actions">
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={saving === k.provider || !inputs[k.provider]}
                    onClick={() => saveKey(k.provider)}
                    title={t("account.saveTooltip")}
                    aria-label={t("account.saveTooltip")}
                  >
                    <Save size={14} />
                  </button>
                  {k.connected && (
                    <>
                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={testing === k.provider}
                        onClick={() => testKey(k.provider)}
                        title={t("account.testTooltip")}
                        aria-label={t("account.testTooltip")}
                      >
                        {testing === k.provider ? <Loader2 size={14} className="spin" /> : <Zap size={14} />}
                      </button>
                      <button className="btn btn-danger-ghost btn-sm" disabled={saving === k.provider} onClick={() => removeKey(k.provider)} title={t("account.deleteTooltip")} aria-label={t("account.deleteTooltip")}>
                        <Trash2 size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title={t("account.connectedProvidersTitle")} icon={CheckCircle2}>
        {keys.some((k) => k.connected) ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {keys.filter((k) => k.connected).map((k) => (
              <div key={k.provider} style={{ fontSize: 13.5, display: "flex", alignItems: "center", gap: 8 }}>
                <CheckCircle2 size={14} color="var(--emerald)" /> {k.label}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sub">{t("account.noProviderConnected")}</p>
        )}
      </Card>
    </div>
  );
}
