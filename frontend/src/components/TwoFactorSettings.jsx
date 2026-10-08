/** Two-factor authentication settings, including the one-time recovery codes for a lost phone. */

import { Copy, Download, KeyRound, ShieldCheck } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { copyToClipboard } from "../utils/copyToClipboard";
import PasswordInput from "./PasswordInput";

function RecoveryCodes({ codes, onDone }) {
  const { t } = useLanguage();
  const { push } = useToast();
  const text = codes.join("\n");
  function download() {
    const url = URL.createObjectURL(new Blob([`AI Crypto Analytics — ${t("twofa.recoveryTitle")}\n\n${text}\n`], { type: "text/plain" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "ai-crypto-analytics-recovery-codes.txt" });
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="recovery-box" data-testid="recovery-codes">
      <p style={{ fontWeight: 600, margin: "0 0 4px" }}>{t("twofa.recoveryTitle")}</p>
      <p className="text-sub" style={{ margin: "0 0 10px" }}>{t("twofa.recoveryText")}</p>
      <ul className="recovery-list mono">{codes.map((c) => <li key={c}>{c}</li>)}</ul>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm"
          onClick={async () => push(t(await copyToClipboard(text) ? "common.copied" : "common.copyFailed"))}>
          <Copy size={13} /> {t("twofa.recoveryCopy")}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={download}><Download size={13} /> {t("twofa.recoveryDownload")}</button>
        <button type="button" className="btn btn-primary btn-sm" onClick={onDone}>{t("twofa.recoverySaved")}</button>
      </div>
    </div>
  );
}

export default function TwoFactorSettings() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { user, patchUser } = useAuth();
  const [setup, setSetup] = useState(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState(null);
  const [left, setLeft] = useState(null);

  useEffect(() => {
    if (user?.totpEnabled && !codes) api.recoveryCodesStatus().then((s) => setLeft(s.left ?? null)).catch(() => setLeft(null));
  }, [user?.totpEnabled, codes]);

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
    const res = await api.totpEnable(code);
    patchUser({ totpEnabled: true });
    setSetup(null);
    setCode("");
    setCodes(Array.isArray(res?.recovery_codes) ? res.recovery_codes : null);
    push(t("twofa.enabled"), "success");
  });
  const disable = () => run(async () => {
    await api.totpDisable(password, code.trim());
    patchUser({ totpEnabled: false });
    setCode("");
    setPassword("");
    push(t("twofa.disabled"), "success");
  });
  const renew = () => run(async () => {
    setCodes(await api.renewRecoveryCodes(password, code.trim()));
    setCode("");
    setPassword("");
  });

  // A 6-digit code from the app, or (to turn 2FA off or renew the codes after losing the phone) a recovery code.
  const codeInput = (allowRecovery) => (
    <div className="field">
      <label>{t(allowRecovery ? "twofa.codeOrRecoveryLabel" : "twofa.codeLabel")}</label>
      <input className="input" inputMode={allowRecovery ? "text" : "numeric"} autoComplete="one-time-code"
        maxLength={allowRecovery ? 11 : 6} value={code} autoCapitalize="none"
        onChange={(e) => setCode(allowRecovery ? e.target.value.replace(/[^0-9A-Za-z -]/g, "") : e.target.value.replace(/\D/g, ""))}
        placeholder="123456" />
    </div>
  );
  const codeReady = code.trim().length >= 6;

  return (
    <div>
      <p style={{ fontWeight: 600, margin: "0 0 4px", display: "flex", alignItems: "center", gap: 6 }}>
        <ShieldCheck size={14} /> {t("twofa.title")}
      </p>
      <p className="text-sub" style={{ margin: "0 0 10px" }}>{user?.totpEnabled ? t("twofa.statusOn") : t("twofa.desc")}</p>
      {codes && <RecoveryCodes codes={codes} onDone={() => { setLeft(codes.length); setCodes(null); }} />}
      {!user?.totpEnabled && !setup && (
        <button className="btn btn-ghost btn-sm" onClick={start} disabled={busy}>{t("twofa.enableButton")}</button>
      )}
      {!user?.totpEnabled && setup && (
        <div>
          <p className="text-sub">{t("twofa.scan")}</p>
          <img src={setup.qr} alt={t("twofa.qrAlt")} width={180} height={180} style={{ background: "#fff", borderRadius: 8, padding: 6 }} />
          <p className="text-sub" style={{ wordBreak: "break-all" }}>{t("twofa.manual")}: <code>{setup.secret}</code></p>
          {codeInput(false)}
          <button className="btn btn-primary btn-sm" onClick={enable} disabled={busy || code.length !== 6}>{t("twofa.confirm")}</button>
        </div>
      )}
      {user?.totpEnabled && !codes && (
        <div>
          {left != null && (
            <p className="text-sub" style={{ margin: "0 0 10px", display: "flex", alignItems: "center", gap: 6 }}>
              <KeyRound size={13} aria-hidden="true" /> {t("twofa.recoveryLeft", { n: left })}
            </p>
          )}
          <div className="grid grid-2">
            <div className="field">
              <label>{t("settings.currentPassword")}</label>
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {codeInput(true)}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-ghost btn-sm" onClick={renew} disabled={busy || !password || !codeReady}>
              {t("twofa.recoveryRenew")}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={disable} disabled={busy || !password || !codeReady}>
              {t("twofa.disableButton")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
