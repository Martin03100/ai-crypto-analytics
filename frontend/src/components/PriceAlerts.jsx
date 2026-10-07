/** Smart alerts: price level, big 24h move, RSI extremes and (Premium) the Fear & Greed index. */

import { BellRing, Crown, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { usePremium } from "../hooks/usePremium";
import { alertLabel, alertValue } from "../utils/alerts";
import { Card } from "./Card";

const KINDS = ["price", "move", "rsi", "fear_greed"];
// Sensible starting values so a new alert is one click away.
const DEFAULTS = { price: "", move: "5", rsi: "70", fear_greed: "25" };
const RANGES = { price: [0, 1e9], move: [0.5, 100], rsi: [1, 99], fear_greed: [1, 99] };

export default function PriceAlerts() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { mode, active: premium } = usePremium();
  const [data, setData] = useState(null);
  const [kind, setKind] = useState("price");
  const [coin, setCoin] = useState("BTC");
  const [direction, setDirection] = useState("above");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.alerts().then(setData).catch(() => setData(null)), []);
  useEffect(() => { load(); }, [load]);

  if (!data) return null;
  const full = data.active >= data.max;
  const premiumKinds = data.premium_kinds || ["fear_greed"];
  const kinds = KINDS.filter((k) => mode || !premiumKinds.includes(k));
  const locked = premiumKinds.includes(kind) && !premium;

  const pickKind = (k) => {
    setKind(k);
    setValue(DEFAULTS[k]);
    if (k === "rsi") setDirection("above");
    if (k === "fear_greed") setDirection("below");
  };

  const add = async (e) => {
    e.preventDefault();
    const num = Number(String(value).replace(",", "."));
    const [low, high] = RANGES[kind];
    if (!Number.isFinite(num) || num < low || num <= 0 || num > high) {
      push(t("alerts.outOfRange"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      await api.createAlert(kind === "fear_greed" ? "ALL" : coin, direction, num, kind);
      setValue(DEFAULTS[kind]);
      push(t("alerts.created"), "success", { translated: true });
      load();
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    try {
      await api.deleteAlert(id);
      load();
    } catch (err) {
      push(err?.message || "error", "error");
    }
  };

  const dirOptions = kind === "move"
    ? [["above", t("alerts.moveUp")], ["below", t("alerts.moveDown")]]
    : [["above", t("alerts.above")], ["below", t("alerts.below")]];

  return (
    <Card title={t("alerts.title")} icon={BellRing} style={{ marginTop: 16 }}>
      <p className="text-sub" style={{ marginTop: 0 }}>{t(premium ? "alerts.introPremium" : "alerts.intro")}</p>
      <div className="tabs alert-kinds" role="tablist" aria-label={t("alerts.kind")}>
        {kinds.map((k) => (
          <button key={k} type="button" role="tab" aria-selected={kind === k} className={`tab ${kind === k ? "active" : ""}`} onClick={() => pickKind(k)}>
            {premiumKinds.includes(k) && <Crown size={12} style={{ marginRight: 4 }} />}{t(`alerts.kind_${k}`)}
          </button>
        ))}
      </div>
      <p className="text-sub alert-hint">{t(`alerts.hint_${kind}`)}</p>
      {locked ? (
        <p className="text-sub">{t("alerts.premiumKind")} <Link to="/premium" className="key-link">{t("gate.cta")}</Link></p>
      ) : (
        <form className="alert-form" onSubmit={add}>
          {kind !== "fear_greed" && (
            <select className="select" value={coin} onChange={(e) => setCoin(e.target.value)} aria-label={t("forecast.coinLabel")}>
              {data.coins.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          )}
          <select className="select" value={direction} onChange={(e) => setDirection(e.target.value)} aria-label={t("alerts.direction")}>
            {dirOptions.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <input className="input" inputMode="decimal" placeholder={t(`alerts.placeholder_${kind}`)} aria-label={t(`alerts.placeholder_${kind}`)}
                 value={value} onChange={(e) => setValue(e.target.value)} />
          <button className="btn btn-primary btn-sm" type="submit" disabled={busy || full}>{t("alerts.add")}</button>
        </form>
      )}
      <p className="text-sub alert-limit">
        {t("alerts.limit", { n: data.active, max: data.max })}
        {full && mode && !premium && <> · <Link to="/premium" className="key-link">{t("alerts.upgrade")}</Link></>}
      </p>
      {data.items.length > 0 && (
        <ul className="alert-list">
          {data.items.map((a) => (
            <li key={a.id} className={a.active ? "" : "alert-done"}>
              <span>
                <strong>{alertLabel(a, t)}</strong>
                {!a.active && a.triggered_price != null && <span className="text-sub"> · {t("alerts.fired", { price: alertValue(a.kind, a.triggered_price) })}</span>}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => remove(a.id)} aria-label={t("common.delete")}><Trash2 size={13} /></button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
