import { ShieldCheck } from "lucide-react";
import QRCode from "qrcode";
import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import PasswordInput from "./PasswordInput";

/** Zapnutie / vypnutie 2FA (TOTP) v Nastaveniach. 2FA sa aktivuje az po
 * overeni prveho kodu, aby sa pouzivatel omylom nezamkol mimo uctu. */
export default function TwoFactorSettings() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { user, patchUser } = useAuth();
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setBusy(true);
    try {
      await action();
    } catch (err) {
      push(err, "error");
    } finally {
      setBusy(false);
    }
  }

  const start = () => run(async () => {
    const res = await api.totpSetup();
    setSetup({ secret: res.secret, qr: await QRCode.toDataURL(res.otpauth_uri, { margin: 1, width: 180 }) });
  });
  const enable = () => run(async () => {
    await api.totpEnable(code);
    patchUser({ totpEnabled: true });
    setSetup(null);
    setCode("");
    push(t("twofa.enabled"), "success");
  });
  const disable = () => run(async () => {
    await api.totpDisable(password, code);
    patchUser({ totpEnabled: false });
    setCode("");
    setPassword("");
    push(t("twofa.disabled"), "success");
  });

  const codeInput = (
    <div className="field">
      <label>{t("twofa.codeLabel")}</label>
      <input className="input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="123456" />
    </div>
  );

  return (
    <div>
      <p style={{ fontWeight: 600, margin: "0 0 4px", display: "flex", alignItems: "center", gap: 6 }}>
        <ShieldCheck size={14} /> {t("twofa.title")}
      </p>
      <p className="text-sub" style={{ margin: "0 0 10px" }}>{user?.totpEnabled ? t("twofa.statusOn") : t("twofa.desc")}</p>
      {!user?.totpEnabled && !setup && (
        <button className="btn btn-ghost btn-sm" onClick={start} disabled={busy}>{t("twofa.enableButton")}</button>
      )}
      {!user?.totpEnabled && setup && (
        <div>
          <p className="text-sub">{t("twofa.scan")}</p>
          <img src={setup.qr} alt={t("twofa.qrAlt")} width={180} height={180} style={{ background: "#fff", borderRadius: 8, padding: 6 }} />
          <p className="text-sub" style={{ wordBreak: "break-all" }}>{t("twofa.manual")}: <code>{setup.secret}</code></p>
          {codeInput}
          <button className="btn btn-primary btn-sm" onClick={enable} disabled={busy || code.length !== 6}>{t("twofa.confirm")}</button>
        </div>
      )}
      {user?.totpEnabled && (
        <div>
          <div className="grid grid-2">
            <div className="field">
              <label>{t("settings.currentPassword")}</label>
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {codeInput}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={disable} disabled={busy || !password || code.length !== 6}>
            {t("twofa.disableButton")}
          </button>
        </div>
      )}
    </div>
  );
}
