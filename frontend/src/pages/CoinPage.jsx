/** Public SEO page for one coin: live price, the free model's outlook, market signals and AI accuracy. */

import { ArrowLeft, ArrowRight, BarChart3, Target } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router-dom";
import { api } from "../api";
import { Card } from "../components/Card";
import SignalList from "../components/SignalList";
import { SkeletonLines } from "../components/Skeleton";
import { useLanguage } from "../context/LanguageContext";
import { formatPrice } from "../utils/formatPrice";
import { QUANT_LABEL } from "../utils/models";
import { SEO_COINS, coinBySlug, coinPath, langFromPath } from "../utils/seoCoins";

const pct = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)} %`);
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");

export function CoinIndex() {
  const { t, setLang } = useLanguage();
  const lang = langFromPath(useLocation().pathname);
  useEffect(() => { setLang(lang); }, [lang, setLang]);
  useEffect(() => { document.title = t("coin.indexTitle"); }, [t]);
  return (
    <main className="standalone-page coin-page">
      <Link to="/" className="key-link standalone-back"><ArrowLeft size={14} /> AI Crypto Analytics</Link>
      <h1 className="standalone-title">{t("coin.indexTitle")}</h1>
      <p className="text-sub">{t("coin.indexIntro")}</p>
      <div className="coin-grid">
        {SEO_COINS.map((c) => (
          <Link key={c.slug} to={coinPath(lang, c.slug)} className="card coin-tile">
            <strong>{c.coin}</strong><span className="text-sub">{c.name}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}

export default function CoinPage() {
  const { t, setLang } = useLanguage();
  const { slug } = useParams();
  const lang = langFromPath(useLocation().pathname);
  const meta = coinBySlug(slug);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => { setLang(lang); }, [lang, setLang]);
  useEffect(() => {
    if (!meta) return undefined;
    let alive = true;
    setData(null);
    setFailed(false);
    api.coinPage(meta.coin).then((d) => alive && setData(d)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, [meta]);
  useEffect(() => {
    if (meta) document.title = t("coin.title", { name: meta.name, coin: meta.coin });
  }, [meta, t]);

  if (!meta) return <Navigate to={coinPath(lang, "").replace(/\/$/, "")} replace />;
  const day = data?.outlook?.find((o) => o.horizon === "24h");
  const week = data?.outlook?.find((o) => o.horizon === "1T");

  return (
    <main className="standalone-page coin-page">
      <Link to={coinPath(lang, "").replace(/\/$/, "")} className="key-link standalone-back"><ArrowLeft size={14} /> {t("coin.allCoins")}</Link>
      <h1 className="standalone-title">{t("coin.title", { name: meta.name, coin: meta.coin })}</h1>
      <p className="text-sub">{t("coin.intro", { name: meta.name })}</p>

      {failed && <p className="text-sub">{t("coin.failed")}</p>}
      {!data && !failed && <SkeletonLines count={6} />}
      {data && (
        <>
          <div className="track-stats track-stats-4">
            <div className="card track-stat"><span className="track-stat-value">{formatPrice(data.price)}</span><span className="text-sub">{t("coin.price")}</span></div>
            <div className="card track-stat"><span className={`track-stat-value ${tone(data.change_24h)}`}>{pct(data.change_24h)}</span><span className="text-sub">24h</span></div>
            <div className="card track-stat"><span className={`track-stat-value ${tone(data.change_7d)}`}>{pct(data.change_7d)}</span><span className="text-sub">7d</span></div>
            <div className="card track-stat"><span className="track-stat-value">{data.rsi ?? "—"}</span><span className="text-sub">RSI (14) · {t(`scanner.signal_${data.signal}`)}</span></div>
          </div>

          <Card title={t("coin.outlookTitle")} icon={BarChart3} style={{ marginTop: 16 }}>
            {[day, week].filter(Boolean).map((o) => (
              <p key={o.horizon} className="coin-outlook">
                <strong>{t(`forecast.horizon${o.horizon}`)}:</strong>{" "}
                <span className={`mono ${tone(o.change_pct)}`}>{formatPrice(o.price)} ({pct(o.change_pct)})</span>
                {o.low != null && <span className="text-sub"> · {t("coin.range", { low: formatPrice(o.low), high: formatPrice(o.high) })}</span>}
              </p>
            ))}
            <p className="text-sub" style={{ marginBottom: 0 }}>{t("coin.outlookNote")}</p>
          </Card>

          {data.signals.length > 0 && (
            <Card title={t("signals.title")} style={{ marginTop: 16 }}>
              <SignalList items={data.signals} compact />
            </Card>
          )}

          <Card title={t("coin.accuracyTitle", { coin: meta.coin })} icon={Target} style={{ marginTop: 16 }}>
            {data.accuracy.length === 0 ? <p className="text-sub" style={{ margin: 0 }}>{t("coin.accuracyEmpty")}</p> : (
              <table className="lb-table">
                <thead><tr><th>{t("leaderboard.colProvider")}</th><th>{t("leaderboard.colEvaluated")}</th><th>{t("leaderboard.colDirection")}</th></tr></thead>
                <tbody>
                  {data.accuracy.map((r) => (
                    <tr key={r.provider}><td>{r.provider === QUANT_LABEL || r.provider === "Statistical model" ? t("provider.quantLabel") : r.provider}</td>
                      <td>{r.forecasts}</td><td>{r.hit_pct}%</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}

      <div className="coin-cta card">
        <strong>{t("coin.ctaTitle", { coin: meta.coin })}</strong>
        <p className="text-sub">{t("coin.ctaText")}</p>
        <Link to="/auth?tab=register" className="btn btn-primary btn-sm">{t("landing.ctaPrimary")} <ArrowRight size={14} /></Link>
      </div>

      <nav className="coin-links" aria-label={t("coin.allCoins")}>
        {SEO_COINS.filter((c) => c.slug !== meta.slug).map((c) => (
          <Link key={c.slug} to={coinPath(lang, c.slug)}>{c.coin}</Link>
        ))}
      </nav>
      <p className="text-sub standalone-disclaimer">{t("track.disclaimer")}</p>
    </main>
  );
}
