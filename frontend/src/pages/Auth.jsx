/** Login and registration page. */

import { AlertTriangle, Brain, CheckCircle2, LineChart, Loader2, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api";
import CandlestickArt from "../components/CandlestickArt";
import PasswordInput from "../components/PasswordInput";
import Turnstile from "../components/Turnstile";
import { useAppConfig } from "../context/AppConfigContext";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { usePageTitle } from "../hooks/usePageTitle";
import { humanizeError } from "../i18n/errorMessages";

const LANG_SQUARES = [
  { code: "sk", label: "SK" },
  { code: "cs", label: "CZ" },
  { code: "en", label: "ENG" },
];

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
  const [tab, setTab] = useState(() => (new URLSearchParams(window.location.search).get("tab") === "register" ? "register" : "login"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [email, setEmail] = useState("");
  const [forgotEmail, setForgotEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState(() => {
    try {
      return sessionStorage.getItem("aca_session_expired") === "1" ? "__expired__" : "";
    } catch { return ""; }
  });
  useEffect(() => {
    try { sessionStorage.removeItem("aca_session_expired"); } catch {  }
  }, []);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [needTotp, setNeedTotp] = useState(false);
  const [needCaptcha, setNeedCaptcha] = useState(false);
  const [totpCode, setTotpCode] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [captchaKey, setCaptchaKey] = useState(0);
  const { login, register } = useAuth();
  const { signups_enabled } = useAppConfig();
  const { t, lang } = useLanguage();
  usePageTitle("auth.pageTitle");
  const navigate = useNavigate();

  function clientValidate() {
    if (!username || !password) return t("auth.validationUsernameRequired");
    if (username.trim().length < 3) return t("auth.validationUsernameLength");
    if (tab === "register" && !/^[A-Za-z0-9_.-]{3,32}$/.test(username.trim())) return t("auth.validationUsernameChars");
    if (password.length < 8) return t("auth.validationPasswordLength");
    if (tab === "register" && password !== confirm) return t("auth.validationPasswordMismatch");
    if (tab === "register" && (!email || !email.includes("@") || !email.split("@").pop().includes(".")))
      return t("auth.validationEmailRequired");
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
        try {
          await login(username, password, needTotp ? totpCode.trim() : undefined, needCaptcha ? captchaToken : undefined);
        } finally {
          if (needCaptcha) {        // a Turnstile token works once
            setCaptchaToken("");
            setCaptchaKey((k) => k + 1);
          }
        }
        navigate("/forecast");
      } else {
        try {
          await register(username, password, email, captchaToken);
        } finally {
          setCaptchaToken("");
          setCaptchaKey((k) => k + 1);
        }
        navigate("/dashboard");    // new users first choose the beginner or full view there
      }
    } catch (err) {
      if (err?.code === "totp_required" || /6-miestny k[oó]d z overovacej aplik/i.test(err?.message || "")) setNeedTotp(true);
      if (err?.code === "captcha_required") setNeedCaptcha(true);
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  async function requestCode(targetEmail) {
    const res = await api.forgotPassword(targetEmail, captchaToken);
    setCaptchaToken("");
    setCaptchaKey((k) => k + 1);
    setInfo(t("auth.forgotSent") + (res.dev_reset_code ? t("auth.devResetCodeNote", { code: res.dev_reset_code }) : ""));
  }

  async function handleForgotPassword(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (!forgotEmail || !forgotEmail.includes("@") || !forgotEmail.split("@").pop().includes(".")) {
      setError(t("auth.validationEmailRequired"));
      return;
    }
    setLoading(true);
    try {
      await requestCode(forgotEmail);
      setCode("");
      setTab("verifyCode");
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    setError("");
    setInfo("");
    setResending(true);
    try {
      await requestCode(forgotEmail);
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setResending(false);
    }
  }

  async function handleVerifyCode(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (code.trim().length !== 6) {
      setError(t("auth.validationCodeLength"));
      return;
    }
    setLoading(true);
    try {
      await api.verifyResetCode(forgotEmail, code.trim());
      setInfo("");
      setTab("reset");
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
      await api.resetPassword(forgotEmail, code.trim(), newPassword);
      setInfo(t("auth.passwordResetDone"));
      setTab("login");
    } catch (err) {
      setError(humanizeError(err, lang));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <AuthLanguageSwitch />
      <div className="auth-brand-panel">
        <div className="auth-brand-glow" aria-hidden="true" />
        <div className="auth-brand-content">
          <div className="brand-mark auth-brand-mark"><LineChart size={22} /></div>
          <h1 className="auth-brand-title">{t("auth.brandTitle")}</h1>
          <p className="auth-brand-sub">{t("auth.brandTagline")}</p>
          <CandlestickArt />
          <div className="auth-feature-list">
            <div className="auth-feature auth-feature-highlight"><PlayCircle size={15} /> {t("auth.featureFreeTrial")}</div>
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
            {tab !== "reset" && tab !== "verifyCode" && (
            <div className="tabs" style={{ width: "100%" }}>
              <button className={`tab ${tab === "login" ? "active" : ""}`} style={{ flex: 1 }} onClick={() => { setTab("login"); setError(""); setInfo(""); }}>
                {t("auth.login")}
              </button>
              <button className={`tab ${tab === "register" ? "active" : ""}`} style={{ flex: 1 }} onClick={() => { setTab("register"); setError(""); setInfo(""); }}>
                {t("auth.register")}
              </button>
            </div>
          )}

          {tab === "register" && !signups_enabled && <div className="alert alert-warn">{t("auth.signupsClosed")}</div>}
          {error && <div className="alert alert-error">{error}</div>}
          {info && <div className={`alert ${info === "__expired__" ? "alert-warn" : "alert-success"}`}>{info === "__expired__" ? <AlertTriangle size={14} style={{ marginRight: 6 }} /> : <CheckCircle2 size={14} style={{ marginRight: 6 }} />}{info === "__expired__" ? t("auth.sessionExpiredNote") : info}</div>}
          {(tab !== "login" || needCaptcha) && <Turnstile key={captchaKey} onToken={setCaptchaToken} />}

          {(tab === "login" || tab === "register") && (
            <form onSubmit={handleSubmit}>
              <div className="field">
                <label>{t("auth.username")}</label>
                <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder={t("auth.usernamePlaceholder")}
                  autoComplete="username" maxLength={tab === "register" ? 32 : 64} />
              </div>
              {tab === "register" && (
                <div className="field">
                  <label>{t("auth.email")}</label>
                  <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("auth.emailPlaceholder")} autoComplete="email" maxLength={255} />
                </div>
              )}
              <div className="field">
                <label>{t("auth.password")}</label>
                <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t("auth.passwordPlaceholder")}
                  autoComplete={tab === "register" ? "new-password" : "current-password"} />
              </div>
              {tab === "login" && needTotp && (
                <div className="field">
                  <label>{t("auth.totpLabel")}</label>
                  <input className="input" autoComplete="one-time-code" maxLength={11} value={totpCode} autoCapitalize="none"
                    onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9A-Za-z -]/g, ""))} placeholder="123456" autoFocus />
                  <span className="text-sub" style={{ display: "block", marginTop: 4 }}>{t("auth.totpRecoveryHint")}</span>
                </div>
              )}
              {tab === "register" && (
                <div className="field">
                  <label>{t("auth.confirmPassword")}</label>
                  <PasswordInput value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
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
                <label>{t("auth.email")}</label>
                <input className="input" type="email" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} placeholder={t("auth.emailPlaceholder")} autoComplete="email" maxLength={255} />
              </div>
              <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                {loading && <Loader2 size={15} className="spin" />} {t("auth.sendCode")}
              </button>
              <button type="button" className="link-btn" onClick={() => { setTab("login"); setError(""); setInfo(""); }}>
                {t("auth.backToLogin")}
              </button>
            </form>
          )}

          {tab === "verifyCode" && (
            <form onSubmit={handleVerifyCode}>
              <p className="text-sub" style={{ marginTop: 0 }}>
                {t("auth.verifyCodeInstructions", { email: forgotEmail })}
              </p>
              <div className="field">
                <label>{t("auth.codeLabel")}</label>
                <input
                  className="input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="000000"
                  style={{ textAlign: "center", fontSize: 22, letterSpacing: 8, fontFamily: "var(--font-mono)" }}
                />
              </div>
              <button className="btn btn-primary btn-block" type="submit" disabled={loading}>
                {loading && <Loader2 size={15} className="spin" />} {t("auth.verifyCode")}
              </button>
              <button type="button" className="link-btn" onClick={handleResendCode} disabled={resending}>
                {resending && <Loader2 size={13} className="spin" style={{ marginRight: 4 }} />} {t("auth.resendCode")}
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
                <PasswordInput value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder={t("auth.passwordPlaceholder")} autoComplete="new-password" />
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
    </main>
  );
}
