/** Public tipster profile: duels with the AI, win rate, streak and weekly challenge results. */

import { ArrowLeft, Flame, Swords, Trophy, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import AmbassadorBadge from "../components/AmbassadorBadge";
import { Card } from "../components/Card";
import LoadError from "../components/LoadError";
import ShareBar from "../components/ShareBar";
import { SkeletonLines } from "../components/Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";
import { formatPrice } from "../utils/formatPrice";
import { usePageTitle } from "../hooks/usePageTitle";

const OUTCOME_BADGE = { win: "badge-buy", loss: "badge-sell", tie: "badge-neutral" };

export default function TipsterProfile() {
  const { nickname } = useParams();
  const { t, lang } = useLanguage();
  usePageTitle("tipster.pageTitle");
  const locale = localeForLang(lang);
  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");

  const load = useCallback(() => {
    setState("loading");
    api.tipster(nickname).then((d) => { setData(d); setState("ok"); })
      .catch((err) => setState(err?.status === 404 ? "missing" : "failed"));
  }, [nickname]);
  useEffect(load, [load]);

  const d = data?.duels || {};
  const date = (iso) => (iso ? new Date(iso).toLocaleDateString(locale, { day: "numeric", month: "short" }) : "—");

  return (
    <main className="standalone-page">
      <Link to="/track-record" className="key-link standalone-back"><ArrowLeft size={14} /> {t("tipster.back")}</Link>
      {state === "loading" && <SkeletonLines count={6} />}
      {state === "failed" && <LoadError onRetry={load} />}
      {state === "missing" && (
        <Card><p className="text-sub">{t("tipster.missing")}</p></Card>
      )}
      {state === "ok" && data && (
        <>
          <div className="tipster-head">
            <div className="tipster-avatar" aria-hidden="true"><UserRound size={22} /></div>
            <div>
              <h1 className="standalone-title" style={{ margin: 0 }}>{data.nickname} <AmbassadorBadge level={data.badge} /></h1>
              {data.member_since && <p className="text-sub" style={{ margin: "2px 0 0" }}>
                {t("tipster.since", { date: new Date(data.member_since).toLocaleDateString(locale, { month: "long", year: "numeric" }) })}
              </p>}
            </div>
          </div>

          <div className="track-stats track-stats-4" style={{ marginTop: 16 }}>
            <div className="card track-stat"><span className="track-stat-value">{d.win_pct == null ? "—" : `${d.win_pct}%`}</span><span className="text-sub">{t("tipster.winRate")}</span></div>
            <div className="card track-stat"><span className="track-stat-value">{d.win ?? 0}/{d.total ?? 0}</span><span className="text-sub">{t("tipster.duelsWon")}</span></div>
            <div className="card track-stat"><span className="track-stat-value"><Flame size={18} aria-hidden="true" /> {d.streak ?? 0}</span><span className="text-sub">{t("tipster.streak")}</span></div>
            <div className="card track-stat"><span className="track-stat-value"><Trophy size={18} aria-hidden="true" /> {data.challenge.wins || 0}</span><span className="text-sub">{t("tipster.challengeWins")}</span></div>
          </div>

          <Card title={t("tipster.recentTitle")} icon={Swords} style={{ marginTop: 16 }}>
            {data.recent.length === 0 ? <p className="text-sub">{t("tipster.noDuels")}</p> : (
              <div className="table-scroll">
                <table className="lb-table">
                  <thead><tr><th>{t("tipster.colDate")}</th><th>{t("tipster.colCoin")}</th><th>{t("tipster.colTip")}</th><th>{t("tipster.colAi")}</th><th>{t("tipster.colActual")}</th><th>{t("tipster.colResult")}</th></tr></thead>
                  <tbody>
                    {data.recent.map((r, i) => (
                      <tr key={`${r.at}-${i}`}>
                        <td>{date(r.at)}</td>
                        <td>{r.coin} · {t(`forecast.horizon${r.horizon}`)}</td>
                        <td className="mono">{formatPrice(r.tip)}</td>
                        <td className="mono">{formatPrice(r.ai)}</td>
                        <td className="mono">{r.actual == null ? "—" : formatPrice(r.actual)}</td>
                        <td><span className={`badge ${OUTCOME_BADGE[r.outcome] || "badge-neutral"}`}>{t(`tipster.outcome_${r.outcome}`)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={t("tipster.challengeTitle")} icon={Trophy} style={{ marginTop: 16 }}>
            {data.challenge.rounds.length === 0 ? <p className="text-sub">{t("tipster.noRounds")}</p> : (
              <ul className="tipster-rounds">
                {data.challenge.rounds.map((r) => (
                  <li key={r.week}>
                    <span className="mono">{r.week}</span> · {r.coin}: {formatPrice(r.guess)} → {formatPrice(r.end)}
                    <span className="text-sub"> ({t("tipster.off", { pct: r.error_pct })})</span>
                    {r.won && <span className="challenge-badge"><Trophy size={11} aria-hidden="true" /> {t("tipster.won")}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div style={{ marginTop: 16 }}><ShareBar text={t("tipster.shareText", { name: data.nickname })} /></div>
          <p className="text-sub" style={{ marginTop: 16 }}>{t("tipster.cta")} <Link to="/auth" className="key-link">{t("tipster.ctaLink")}</Link></p>
        </>
      )}
    </main>
  );
}
