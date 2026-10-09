/** Settings: plan, invite link and badge, Telegram, public nickname and the e-mail options. */

import { Copy, Crown, Gift, Mail, Send, Sun, Trophy, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAppConfig } from "../context/AppConfigContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePremium } from "../hooks/usePremium";
import { localeForLang } from "../i18n/locale";
import { copyToClipboard } from "../utils/copyToClipboard";
import AmbassadorBadge from "./AmbassadorBadge";
import InviteQr from "./InviteQr";
import { Card } from "./Card";

const NEXT_BADGE = [[1, "bronze"], [5, "silver"], [10, "gold"]];

function Divider() {
  return <hr className="divider" />;
}

export default function MembershipCard() {
  const { t, lang } = useLanguage();
  const { referrals_enabled, digest_enabled } = useAppConfig();
  const { mode } = usePremium();
  const { push } = useToast();
  const [m, setM] = useState(null);
  const [nickname, setNickname] = useState("");
  const [busy, setBusy] = useState(false);
  const [tgUrl, setTgUrl] = useState(null);

  const load = useCallback(() => api.membership().then((data) => { setM(data); setNickname(data.nickname || ""); }).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  if (!m) return null;
  const fail = (err) => push(err?.message || "error", "error");

  const saveNickname = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.setNickname(nickname.trim());
      setM((prev) => ({ ...prev, nickname: res.nickname }));
      push(t("membership.nicknameSaved"), "success", { translated: true });
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (key) => async () => {
    const next = !m[key];
    setM((prev) => ({ ...prev, [key]: next }));
    try {
      await api.setPreferences({ [key]: next });
    } catch (err) {
      setM((prev) => ({ ...prev, [key]: !next }));
      fail(err);
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
      fail(err);
    }
  };

  const linkTelegram = async () => {
    try {
      setTgUrl((await api.telegramLink()).url);
    } catch (err) {
      fail(err);
    }
  };

  const unlinkTelegram = async () => {
    try {
      await api.telegramUnlink();
      setTgUrl(null);
      load();
    } catch (err) {
      fail(err);
    }
  };

  const until = m.premium_until ? new Date(m.premium_until).toLocaleDateString(localeForLang(lang)) : null;
  const next = NEXT_BADGE.find(([n]) => m.referral_signups < n);
  // The paid extras (Telegram, morning e-mail) are free for everyone while Premium mode is off.
  const features = Boolean(m.features ?? m.premium);
  const showTelegram = (mode || features) && m.telegram?.available;

  return (
    <Card title={t(mode ? "membership.title" : "membership.titleFree")} icon={mode ? Crown : UserRound}>
      {mode && (
        <>
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
          <Divider />
        </>
      )}

      {referrals_enabled && (
        <>
          <h3 className="membership-h"><Gift size={14} /> {t("membership.inviteTitle")} <AmbassadorBadge level={m.badge} />
            {m.challenge_wins > 0 && <span className="challenge-badge" title={t("weekly.winsTitle")}><Trophy size={12} /> {m.challenge_wins}×</span>}</h3>
          <p className="text-sub">
            {mode
              ? t("membership.inviteTextPremium", { days: m.referral_days, trial: m.referral_trial_days })
              : t("membership.inviteTextFree")}
          </p>
          <div className="invite-row">
            <input className="input mono" readOnly value={m.referral_link} aria-label={t("membership.inviteTitle")} onFocus={(e) => e.target.select()} />
            <button className="btn btn-ghost btn-sm" onClick={copyInvite}><Copy size={13} /> {t("shareBar.copy")}</button>
          </div>
          <div style={{ marginTop: 8 }}><InviteQr link={m.referral_link} /></div>
          <p className="text-sub" style={{ marginTop: 6 }}>
            {t("membership.inviteSignups", { n: m.referral_signups })}
            {next && <> · {t("membership.nextBadge", { n: next[0] - m.referral_signups, badge: t(`badge.${next[1]}`) })}</>}
            {mode && m.referrals_rewarded > 0 && <> · {t("membership.inviteRewarded", { n: m.referrals_rewarded, max: m.referrals_max })}</>}
          </p>
          <Divider />
        </>
      )}

      <h3 className="membership-h"><UserRound size={14} /> {t("membership.nicknameTitle")}</h3>
      <p className="text-sub">{t("membership.nicknameText")}</p>
      <form className="invite-row" onSubmit={saveNickname}>
        <input className="input" value={nickname} maxLength={20} placeholder={t("membership.nicknamePlaceholder")}
               aria-label={t("membership.nicknameTitle")} onChange={(e) => setNickname(e.target.value)} />
        <button className="btn btn-ghost btn-sm" type="submit" disabled={busy}>{t("common.save")}</button>
      </form>

      {showTelegram && (
        <>
          <Divider />
          <h3 className="membership-h"><Send size={14} /> Telegram</h3>
          <p className="text-sub">{t("membership.telegramText")}</p>
          {m.telegram.linked ? (
            <div className="invite-row">
              <span className="badge badge-buy"><span className="badge-dot" /> {t("membership.telegramLinked")}</span>
              <button className="btn btn-ghost btn-sm" onClick={unlinkTelegram}>{t("membership.telegramUnlink")}</button>
            </div>
          ) : !features ? (
            <Link to="/premium" className="key-link">{t("gate.cta")}</Link>
          ) : tgUrl ? (
            <div className="invite-row">
              <a href={tgUrl} target="_blank" rel="noopener noreferrer" className="btn btn-primary btn-sm"><Send size={13} /> {t("membership.telegramOpen")}</a>
              <button className="btn btn-ghost btn-sm" onClick={load}>{t("membership.telegramCheck")}</button>
            </div>
          ) : (
            <button className="btn btn-ghost btn-sm" onClick={linkTelegram}><Send size={13} /> {t("membership.telegramConnect")}</button>
          )}
        </>
      )}

      {(mode || features) && (
        <>
          <Divider />
          <label className={`toggle-row ${features ? "" : "toggle-locked"}`}>
            <input type="checkbox" checked={m.briefing_opt_in} disabled={!features} onChange={toggle("briefing_opt_in")} />
            <span>
              <strong><Sun size={13} style={{ verticalAlign: -2, marginRight: 4 }} />{t(mode ? "membership.briefingTitlePremium" : "membership.briefingTitle")}</strong>
              <span className="text-sub" style={{ display: "block" }}>
                {t("membership.briefingText")} {mode && !features && <Link to="/premium" className="key-link">{t("gate.cta")}</Link>}
              </span>
            </span>
          </label>
        </>
      )}

      {digest_enabled && (
        <>
          <Divider />
          <label className="toggle-row">
            <input type="checkbox" checked={m.digest_opt_in} onChange={toggle("digest_opt_in")} />
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
