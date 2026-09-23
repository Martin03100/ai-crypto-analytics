import { Brain, CheckCircle2, LineChart, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api } from "../api";
import CandlestickArt from "../components/CandlestickArt";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { humanizeError } from "../i18n/errorMessages";

const LANG_SQUARES = [
  { code: "sk", label: "SK" },
  { code: "cs", label: "CZ" },
  { code: "en", label: "ENG" },
];

/** Tri male stvorceky (SK / CZ / ENG) v pravom dolnom rohu prihlasovacej
 * obrazovky. Vyber sa aplikuje okamzite (LanguageContext prekresli cely
 * strom) a zaroven sa hned uklada do localStorage (viz setLang). */
function AuthLanguageSwitch() {
  const { lang, setLang } = useLanguage();
  return (
    <div className="auth-lang-switch" role="group" aria-label="Language / Jazyk">
      {LANG_SQUARES.map((l) => (
        <button
          key={l.code}
          type="button"
          className={`auth-lang-btn ${lang === l.code ? "active" : ""}`}
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          title={l.label}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export default function Auth() {
  const [searchParams] = useSearchParams();
  const resetTokenFromUrl = searchParams.get("resetToken");

  const [tab, setTab] = useState(resetTokenFromUrl ? "reset" : "login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const { t, lang } = useLanguage();
  usePageTitle("auth.pageTitle");
  const navigate = useNavigate();

  function clientValidate() {
    if (!username || !password) return t("auth.validationUsernameRequired");
    if (username.trim().length < 3) return t("auth.validationUsernameLength");
    if (password.length < 8) return t("auth.validationPasswordLength");
    if (tab === "register" && password !== confirm) return t("auth.validationPasswordMismatch");
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    const validationError = clientValidate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      if (tab === "login") {
        await login(username, password);
      } else {
        await register(username, password);
      }
      navigate("/forecast");
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  async function handleForgotPassword(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!username || username.trim().length < 3) {
      setError(t("auth.validationUsernameRequiredForgot"));
      return;
    }
    setLoading(true);
    try {
      const res = await api.forgotPassword(username);
      setInfo(res.message + (res.dev_reset_link ? t("auth.devResetLinkNote", { link: res.dev_reset_link }) : ""));
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (newPassword.length < 8) {
      setError(t("auth.validationNewPasswordLength"));
      return;
    }
    setLoading(true);
    try {
      const res = await api.resetPassword(resetTokenFromUrl, newPassword);
      setInfo(res.message);
      setTab("login");
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <AuthLanguageSwitch />
      <div className="auth-brand-panel">
        <div className="auth-brand-glow" aria-hidden="true" />
        <div className="auth-brand-content">
          <div className="brand-mark auth-brand-mark"><LineChart size={22} /></div>
          <h1 className="auth-brand-title">{t("auth.brandTitle")}</h1>
          <p className="auth-brand-sub">{t("auth.brandTagline")}</p>
          <CandlestickArt />
          <div className="auth-feature-list">
            <div className="auth-feature"><Brain size={15} /> {t("auth.featureModels")}</div>
            <div className="auth-feature"><Sparkles size={15} /> {t("auth.featurePortfolio")}</div>
            <div className="auth-feature"><ShieldCheck size={15} /> {t("auth.featureSecurity")}</div>
          </div>
        </div>
      </div>

      <div className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-hero auth-hero-mobile-only">
            <div className="brand-mark"><LineChart size={22} /></div>
            <h1>{t("auth.brandTitle")}</h1>
            <p>{t("auth.brandTaglineMobile")}</p>
          </div>

          <div className="card auth-form-card">
            {tab !== "reset" && (
            <div className="tabs" style={{ width: "100%" }}>
              <button className={`tab ${tab === "login" ? "active" : ""}`} style={{ flex: 1 }} onClick={() => { setTab("login"); setError(""); setInfo(""); }}>
                {t("auth.login")}
              </button>
              <button className={`tab ${tab === "register" ? "active" : ""}`} style={{ flex: 1 }} onClick={() => { setTab("register"); setError(""); setInfo(""); }}>
                {t("auth.register")}
              </button>
            </div>
          )}

          {error && <div className="alert alert-error">{error}</div>}
          {info && <div className="alert alert-success"><CheckCircle2 size={14} style={{ marginRight: 6 }} />{info}</div>}

          {(tab === "login" || tab === "register") && (
            <form onSubmit={handleSubmit}>
              <div className="field">
                <label>{t("auth.username")}</label>
                <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder={t("auth.usernamePlaceholder")} />
              </div>
              <div className="field">
                <label>{t("auth.password")}</label>
                <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t("auth.passwordPlaceholder")} />
              </div>
              {tab === "register" && (
                <div className="field">
                  <label>{t("auth.confirmPassword")}</label>
                  <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
                </div>
              )}
              <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                {loading && <Loader2 size={15} className="spin" />}
                {tab === "login" ? t("auth.login") : t("auth.register")}
              </button>
              {tab === "login" && (
                <button type="button" className="link-btn" onClick={() => { setTab("forgot"); setError(""); setInfo(""); }}>
                  {t("auth.forgotPasswordLink")}
                </button>
              )}
            </form>
          )}

          {tab === "forgot" && (
            <form onSubmit={handleForgotPassword}>
              <p className="text-sub" style={{ marginTop: 0 }}>
                {t("auth.forgotInstructions")}
              </p>
              <div className="field">
                <label>{t("auth.username")}</label>
                <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                {loading && <Loader2 size={15} className="spin" />} {t("auth.sendResetLink")}
              </button>
              <button type="button" className="link-btn" onClick={() => { setTab("login"); setError(""); setInfo(""); }}>
                {t("auth.backToLogin")}
              </button>
            </form>
          )}

          {tab === "reset" && (
            <form onSubmit={handleResetPassword}>
              <p className="text-sub" style={{ marginTop: 0 }}>{t("auth.resetInstructions")}</p>
              <div className="field">
                <label>{t("auth.newPasswordLabel")}</label>
                <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t("auth.passwordPlaceholder")} />
              </div>
              <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                {loading && <Loader2 size={15} className="spin" />} {t("auth.setNewPassword")}
              </button>
              <button type="button" className="link-btn" onClick={() => { setTab("login"); setError(""); setInfo(""); }}>
                {t("auth.backToLogin")}
              </button>
            </form>
          )}
        </div>
        <div style={{ display: "flex", gap: 14, justifyContent: "center", marginTop: 18, fontSize: 12 }}>
          <Link to="/privacy" className="text-sub" style={{ textDecoration: "none" }}>{t("privacy.title")}</Link>
          <Link to="/terms" className="text-sub" style={{ textDecoration: "none" }}>{t("terms.title")}</Link>
        </div>
        </div>
      </div>
    </div>
  );
}
