/** Premium: your real holdings with buy price, live P&L, allocation, a risk score and a daily value history. */

import { FileDown, Pencil, Plus, ShieldAlert, Trash2, Wallet } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePremium } from "../hooks/usePremium";
import { localeForLang } from "../i18n/locale";
import { COINS } from "../utils/coins";
import { formatPrice, formatUsd } from "../utils/formatPrice";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import LoadError from "./LoadError";
import PremiumGate from "./PremiumGate";
import { SkeletonLines } from "./Skeleton";

const money = (v) => (v == null ? "—" : v < 0 ? `-${formatPrice(-v)}` : formatPrice(v));
const signed = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)} %`);
const tone = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
const parse = (raw) => Number(String(raw).trim().replace(/\s/g, "").replace(",", "."));

export default function PortfolioTracker() {
  const { t, lang } = useLanguage();
  const { push } = useToast();
  const { active } = usePremium();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [coin, setCoin] = useState("BTC");
  const [amount, setAmount] = useState("");
  const [buy, setBuy] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    api.positions().then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(() => { if (active) load(); }, [active, load]);

  if (!active) return <PremiumGate title={t("tracker.title")} text={t("tracker.gate")} />;
  if (failed) return <LoadError onRetry={load} />;
  if (!data) return <Card title={t("tracker.title")} icon={Wallet}><SkeletonLines count={4} /></Card>;

  const save = async (e) => {
    e.preventDefault();
    const a = parse(amount);
    const p = parse(buy);
    if (!(a > 0) || !(p > 0)) {
      push(t("portfolio.validationInvalidNumber"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      setData(await api.savePosition(coin, a, p));
      setAmount("");
      setBuy("");
      push(t("tracker.saved"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  const edit = (r) => {
    setCoin(r.coin);
    setAmount(String(r.amount));
    setBuy(String(r.avg_buy_price));
    document.getElementById("tracker-amount")?.focus();
  };

  const remove = async (id) => {
    try {
      setData(await api.deletePosition(id));
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  const { total, risk } = data;
  const locale = localeForLang(lang);
  const history = data.history.map((h) => ({ ...h, d: new Date(`${h.day}T00:00:00Z`).toLocaleDateString(locale, { day: "numeric", month: "numeric" }) }));
  const full = data.positions.length >= data.max;

  return (
    <>
      <Card title={t("tracker.title")} icon={Wallet}>
        <p className="text-sub" style={{ marginTop: 0 }}>{t("tracker.intro")}</p>
        <form className="tracker-form" onSubmit={save}>
          <select className="select" value={coin} onChange={(e) => setCoin(e.target.value)} aria-label={t("forecast.coinLabel")}>
            {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input id="tracker-amount" className="input" inputMode="decimal" placeholder={t("tracker.amount")} aria-label={t("tracker.amount")}
                 value={amount} onChange={(e) => setAmount(e.target.value)} />
          <input className="input" inputMode="decimal" placeholder={t("tracker.buyPrice")} aria-label={t("tracker.buyPrice")}
                 value={buy} onChange={(e) => setBuy(e.target.value)} />
          <button className="btn btn-primary btn-sm" type="submit" disabled={busy || (full && !data.positions.some((p) => p.coin === coin))}>
            <Plus size={14} /> {t("tracker.save")}
          </button>
        </form>
        <p className="text-sub" style={{ margin: "6px 0 0" }}>{t("tracker.hint")}</p>
      </Card>

      {data.positions.length > 0 && (
        <>
          <div className="track-stats track-stats-4" style={{ marginTop: 16 }}>
            <div className="card track-stat"><span className="track-stat-value">{formatPrice(total.value)}</span><span className="text-sub">{t("tracker.value")}</span></div>
            <div className="card track-stat">
              <span className={`track-stat-value ${tone(total.pnl)}`}>{money(total.pnl)}</span>
              <span className="text-sub">{t("tracker.pnl")} · {signed(total.pnl_pct)}</span>
            </div>
            <div className="card track-stat">
              <span className={`track-stat-value ${tone(total.change_24h_pct)}`}>{signed(total.change_24h_pct)}</span>
              <span className="text-sub">{t("tracker.today")}</span>
            </div>
            <div className="card track-stat">
              <span className={`track-stat-value risk-${risk.level}`}>{risk.score ?? "—"}<small>/10</small></span>
              <span className="text-sub">{t("tracker.risk")} <InfoTip text={t("tracker.riskHelp")} /></span>
            </div>
          </div>
          {data.unpriced > 0 && <p className="text-sub" role="status" style={{ marginTop: 10 }}>{t("tracker.unpriced", { n: data.unpriced })}</p>}
          {risk.top_share_pct > 60 && (
            <div className="alert alert-warn" role="status" style={{ marginTop: 12 }}>
              <ShieldAlert size={14} style={{ marginRight: 6 }} />{t("tracker.concentration", { pct: risk.top_share_pct })}
            </div>
          )}

          <Card title={t("tracker.positions")} style={{ marginTop: 16 }}
                className="tracker-positions">
            <div className="table-scroll">
              <table className="lb-table">
                <thead>
                  <tr><th>{t("scanner.colCoin")}</th><th>{t("tracker.amount")}</th><th>{t("tracker.buyPrice")}</th><th>{t("scanner.colPrice")}</th>
                    <th>{t("tracker.value")}</th><th>{t("tracker.pnl")}</th><th>{t("tracker.share")}</th><th /></tr>
                </thead>
                <tbody>
                  {data.positions.map((r) => (
                    <tr key={r.id}>
                      <td><strong>{r.coin}</strong></td>
                      <td className="mono">{r.amount}</td>
                      <td className="mono">{formatPrice(r.avg_buy_price)}</td>
                      <td className="mono">{r.price ? formatPrice(r.price) : "—"}</td>
                      <td className="mono">{money(r.value)}</td>
                      <td className={`mono ${tone(r.pnl)}`}>{money(r.pnl)} <span className="text-sub">({signed(r.pnl_pct)})</span></td>
                      <td>
                        {r.allocation_pct == null ? "—" : (
                          <>
                            <div className="alloc"><span style={{ width: `${r.allocation_pct}%` }} /></div>
                            <span className="text-sub">{r.allocation_pct} %</span>
                          </>
                        )}
                      </td>
                      <td className="row-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => edit(r)} aria-label={t("tracker.edit")}><Pencil size={13} /></button>
                        <button className="btn btn-ghost btn-sm" onClick={() => remove(r.id)} aria-label={t("common.delete")}><Trash2 size={13} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <a className="btn btn-ghost btn-sm" href={api.reportPdfUrl()} download style={{ marginTop: 12 }}><FileDown size={14} /> {t("report.download")}</a>
          </Card>

          <Card title={t("tracker.history")} style={{ marginTop: 16 }}>
            {history.length < 2 ? <p className="text-sub" style={{ margin: 0 }}>{t("tracker.historyEmpty")}</p> : (
              <div role="img" aria-label={t("tracker.history")}>
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={history} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="d" stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} minTickGap={24} />
                    <YAxis stroke="var(--text-tertiary)" fontSize={11} tickLine={false} axisLine={false} width={70} domain={["auto", "auto"]}
                           tickFormatter={(v) => formatUsd(v, 0)} />
                    <Tooltip contentStyle={{ background: "var(--bg-tooltip)", border: "1px solid var(--border-strong)", borderRadius: 10, fontSize: 12, color: "var(--text-primary)" }}
                             formatter={(v, key) => [formatPrice(v), key === "value" ? t("tracker.value") : t("tracker.cost")]} />
                    <Area dataKey="value" stroke="#22d3ee" fill="rgba(34,211,238,0.15)" strokeWidth={2} isAnimationActive={false} />
                    <Area dataKey="cost" stroke="#a78bfa" fill="transparent" strokeDasharray="4 3" strokeWidth={1.4} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}
