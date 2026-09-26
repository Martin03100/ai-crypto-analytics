import { Loader2, LogOut, MailCheck } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";

/** Obrazovka po registracii: kym pouzivatel neoveri email kodom, appka mu
 * nepusti dalej (backend to vynucuje aj sam - viz app/deps.py). */
export default function VerifyEmailGate() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { user, patchUser, updateEmail, logout } = useAuth();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [newEmail, setNewEmail] = useState("");

  async function verify(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.verifyEmail(code);
      patchUser({ emailVerified: true });
      push(t("verify.success"), "success");
    } catch (err) {
      push(err, "error");
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    try {
      await api.resendVerification();
      push(t("verify.resent"), "success");
    } catch (err) {
      push(err, "error");
    }
  }

  async function changeEmail(e) {
    e.preventDefault();
    try {
      const res = await api.updateEmail(newEmail.trim());
      updateEmail(res.email, { emailVerified: res.email_verified });
      setEditing(false);
      setCode("");
      push(t("verify.resent"), "success");
    } catch (err) {
      push(err, "error");
    }
  }

  return (
    <div className="verify-gate">
      <div className="card verify-card">
        <div className="verify-icon"><MailCheck size={22} /></div>
        <h2>{t("verify.title")}</h2>
        <p className="text-sub">{t("verify.desc", { email: user?.email || "" })}</p>
        <form onSubmit={verify}>
          <div className="field">
            <label>{t("verify.codeLabel")}</label>
            <input className="input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="123456" autoFocus />
          </div>
          <button className="btn btn-primary btn-block" type="submit" disabled={busy || code.length !== 6}>
            {busy && <Loader2 size={14} className="spin" />} {t("verify.submit")}
          </button>
        </form>
        <div className="verify-actions">
          <button className="btn btn-ghost btn-sm" onClick={resend}>{t("verify.resend")}</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing((v) => !v)}>{t("verify.changeEmail")}</button>
          <button className="btn btn-ghost btn-sm" onClick={logout}><LogOut size={13} /> {t("verify.logout")}</button>
        </div>
        {editing && (
          <form onSubmit={changeEmail} style={{ marginTop: 12 }}>
            <div className="field">
              <input className="input" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                placeholder={t("settings.emailPlaceholder")} aria-label={t("settings.emailLabel")} />
            </div>
            <button className="btn btn-ghost btn-sm" type="submit">{t("verify.changeEmailButton")}</button>
          </form>
        )}
      </div>
    </div>
  );
}
