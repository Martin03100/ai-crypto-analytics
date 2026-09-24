import { AtSign, Info, Key, Languages, LogOut, Moon, ShieldCheck, Sun, Wallet2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { useAuth } from "../context/AuthContext";
import { CURRENCIES, useCurrency } from "../context/CurrencyContext";
import { LANGUAGES } from "../i18n/translations";
import { useLanguage } from "../context/LanguageContext";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { api } from "../api";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Settings() {
  const { t, lang, setLang } = useLanguage();
  usePageTitle("settings.title");
  const { theme, setTheme } = useTheme();
  const { currency, setCurrency } = useCurrency();
  const { logout, user, updateEmail } = useAuth();
  const { push } = useToast();

  const [email, setEmail] = useState(user?.email || "");
  const [savingEmail, setSavingEmail] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  async function handleSaveEmail(e) {
    e.preventDefault();
    setSavingEmail(true);
    try {
      const res = await api.updateEmail(email.trim() || null);
      updateEmail(res.email);
      push(t("settings.emailSaved"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setSavingEmail(false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    if (!currentPassword || newPassword.length < 8) {
      push(t("settings.passwordMinLengthWarning"), "warn");
      return;
    }
    setSavingPassword(true);
    try {
      const res = await api.changePassword(currentPassword, newPassword);
      push(res.message, "success");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      push(err, "error");
    } finally {
      setSavingPassword(false);
    }
  }

  async function handleLogoutAllDevices() {
    setLoggingOutAll(true);
    try {
      const res = await api.logoutAllDevices();
      push(res.message, "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setLoggingOutAll(false);
    }
  }

  return (
    <div>
      <div className="topbar">
        <div>
          <h1 className="page-title">{t("settings.title")}</h1>
          <p className="page-sub">{t("settings.sub")}</p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Card title={t("settings.language")} icon={Languages}>
          <p className="text-sub" style={{ marginTop: 0 }}>{t("settings.languageDesc")}</p>
          <div className="tabs">
            {LANGUAGES.map((l) => (
              <button key={l.code} className={`tab ${lang === l.code ? "active" : ""}`} onClick={() => setLang(l.code)}>
                {l.label}
              </button>
            ))}
          </div>
        </Card>

        <Card title={t("settings.appearance")} icon={theme === "dark" ? Moon : Sun}>
          <div className="tabs">
            <button className={`tab ${theme === "dark" ? "active" : ""}`} onClick={() => setTheme("dark")}>
              <Moon size={14} style={{ marginRight: 6 }} /> {t("settings.dark")}
            </button>
            <button className={`tab ${theme === "light" ? "active" : ""}`} onClick={() => setTheme("light")}>
              <Sun size={14} style={{ marginRight: 6 }} /> {t("settings.light")}
            </button>
          </div>
        </Card>

        <Card title={t("settings.currency")} icon={Wallet2}>
          <p className="text-sub" style={{ marginTop: 0 }}>{t("settings.currencyDesc")}</p>
          <div className="tabs">
            {CURRENCIES.map((c) => (
              <button key={c} className={`tab ${currency === c ? "active" : ""}`} onClick={() => setCurrency(c)}>
                {c}
              </button>
            ))}
          </div>
        </Card>

        <Card title={t("settings.security")} icon={ShieldCheck}>
          <p className="text-sub" style={{ marginTop: 0 }}>{t("settings.sessionInfo")}</p>

          <form onSubmit={handleSaveEmail} style={{ marginTop: 14 }}>
            <div className="field">
              <label><AtSign size={12} style={{ verticalAlign: -1, marginRight: 4 }} />{t("settings.emailLabel")}</label>
              <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("settings.emailPlaceholder")} />
              <span className="text-sub" style={{ display: "block", marginTop: 4 }}>{t("settings.emailDesc")}</span>
            </div>
            <button className="btn btn-ghost btn-sm" type="submit" disabled={savingEmail}>
              {savingEmail ? t("common.saving") : t("settings.saveEmail")}
            </button>
          </form>

          <hr className="divider" />

          <form onSubmit={handleChangePassword}>
            <div className="grid grid-2">
              <div className="field">
                <label>{t("settings.currentPassword")}</label>
                <input className="input" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
              </div>
              <div className="field">
                <label>{t("settings.newPassword")}</label>
                <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t("settings.newPasswordPlaceholder")} />
              </div>
            </div>
            <button className="btn btn-primary btn-sm" type="submit" disabled={savingPassword}>
              <Key size={14} /> {t("settings.changePassword")}
            </button>
          </form>

          <hr className="divider" />

          <button className="btn btn-ghost btn-sm" onClick={handleLogoutAllDevices} disabled={loggingOutAll}>
            <LogOut size={14} /> {t("settings.logoutAllDevices")}
          </button>
        </Card>

        <Card title={t("settings.about")} icon={Info}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
            <div><strong>{t("settings.version")}:</strong> 2.2.0 — 2026 Edition</div>
            <div><strong>{t("settings.techStack")}:</strong> React (Vite), FastAPI, SQLAlchemy, Recharts, CoinGecko API</div>
            <div><strong>{t("settings.support")}:</strong> <a href="mailto:support@example.com" className="key-link">support@example.com</a></div>
            <div style={{ display: "flex", gap: 14, marginTop: 6 }}>
              <Link to="/privacy" className="key-link">{t("privacy.title")}</Link>
              <Link to="/terms" className="key-link">{t("terms.title")}</Link>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
