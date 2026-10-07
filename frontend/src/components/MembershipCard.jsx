/** Settings: Premium status, invite link, public nickname and the weekly email. */

import { Copy, Crown, Gift, Mail, Sun, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { copyToClipboard } from "../utils/copyToClipboard";
import { Card } from "./Card";

export default function MembershipCard() {
  const { t, lang } = useLanguage();
  const { referrals_enabled, digest_enabled } = useAppConfig();
  const { push } = useToast();
  const [m, setM] = useState(null);
  const [nickname, setNickname] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.membership().then((data) => { setM(data); setNickname(data.nickname || ""); }).catch(() => {});
  }, []);

  if (!m) return null;

  const saveNickname = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.setNickname(nickname.trim());
      setM((prev) => ({ ...prev, nickname: res.nickname }));
      push(t("membership.nicknameSaved"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  const toggleBriefing = async () => {
    const next = !m.briefing_opt_in;
    setM((prev) => ({ ...prev, briefing_opt_in: next }));
    try {
      await api.setPreferences({ briefing_opt_in: next });
    } catch (err) {
      setM((prev) => ({ ...prev, briefing_opt_in: !next }));
      push(err?.message || "error", "error");
    }
  };

  const toggleDigest = async () => {
    const next = !m.digest_opt_in;
    setM((prev) => ({ ...prev, digest_opt_in: next }));
    try {
      await api.setPreferences({ digest_opt_in: next });
    } catch (err) {
      setM((prev) => ({ ...prev, digest_opt_in: !next }));
      push(err?.message || "error", "error");
    }
  };

  const copyInvite = async () => {
    const ok = await copyToClipboard(m.referral_link);
    push(t(ok ? "common.copied" : "common.copyFailed"), ok ? "success" : "error", { translated: true });
  };

  const openBilling = async () => {
    try {
      const { url } = await api.billingPortal();
      window.location.assign(url);
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  const until = m.premium_until ? new Date(m.premium_until).toLocaleDateString(localeForLang(lang)) : null;

  return (
    <Card title={t("membership.title")} icon={Crown}>
      <div className="membership-status">
        {m.premium ? (
          <>
            <span className="badge badge-buy"><span className="badge-dot" /> Premium</span>
            <span className="text-sub">{t("membership.activeUntil", { date: until })}</span>
            {m.has_billing && m.billing_enabled && (
              <button className="btn btn-ghost btn-sm" onClick={openBilling}>{t("membership.manageBilling")}</button>
            )}
          </>
        ) : (
          <>
            <span className="badge badge-neutral"><span className="badge-dot" /> {t("membership.free")}</span>
            <Link to="/premium" className="btn btn-primary btn-sm">{t("membership.upgrade")}</Link>
          </>
        )}
      </div>

      {referrals_enabled && (
        <>
          <hr className="divider" />

          <h3 className="membership-h"><Gift size={14} /> {t("membership.inviteTitle")}</h3>
          <p className="text-sub">{t("membership.inviteText", { days: m.referral_days })}</p>
          <div className="invite-row">
            <input className="input mono" readOnly value={m.referral_link} aria-label={t("membership.inviteTitle")} onFocus={(e) => e.target.select()} />
            <button className="btn btn-ghost btn-sm" onClick={copyInvite}><Copy size={13} /> {t("shareBar.copy")}</button>
          </div>
          <p className="text-sub" style={{ marginTop: 6 }}>{t("membership.inviteCount", { n: m.referrals_rewarded, max: m.referrals_max })}</p>
        </>
      )}

      <hr className="divider" />

      <h3 className="membership-h"><UserRound size={14} /> {t("membership.nicknameTitle")}</h3>
      <p className="text-sub">{t("membership.nicknameText")}</p>
      <form className="invite-row" onSubmit={saveNickname}>
        <input className="input" value={nickname} maxLength={20} placeholder={t("membership.nicknamePlaceholder")}
               aria-label={t("membership.nicknameTitle")} onChange={(e) => setNickname(e.target.value)} />
        <button className="btn btn-ghost btn-sm" type="submit" disabled={busy}>{t("common.save")}</button>
      </form>

      <hr className="divider" />

      <label className={`toggle-row ${m.premium ? "" : "toggle-locked"}`}>
        <input type="checkbox" checked={m.briefing_opt_in} disabled={!m.premium} onChange={toggleBriefing} />
        <span>
          <strong><Sun size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{t("membership.briefingTitle")}</strong>
          <span className="text-sub" style={{ display: "block" }}>
            {t("membership.briefingText")} {!m.premium && <Link to="/premium" className="key-link">{t("gate.cta")}</Link>}
          </span>
        </span>
      </label>

      {digest_enabled && (
        <>
          <hr className="divider" />

          <label className="toggle-row">
            <input type="checkbox" checked={m.digest_opt_in} onChange={toggleDigest} />
            <span>
              <strong><Mail size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{t("membership.digestTitle")}</strong>
              <span className="text-sub" style={{ display: "block" }}>{t("membership.digestText")}</span>
            </span>
          </label>
        </>
      )}
    </Card>
  );
}
