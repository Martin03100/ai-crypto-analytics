/** Price alerts: get notified (in the app and by email) when a coin crosses a price. */

import { BellRing, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { formatPrice } from "../utils/formatPrice";
import { Card } from "./Card";

export default function PriceAlerts() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  const [data, setData] = useState(null);
  const [coin, setCoin] = useState("BTC");
  const [direction, setDirection] = useState("above");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.alerts().then(setData).catch(() => setData(null)), []);
  useEffect(() => { load(); }, [load]);

  if (!data) return null;
  const full = data.active >= data.max;

  const add = async (e) => {
    e.preventDefault();
    const value = Number(String(price).replace(",", "."));
    if (!Number.isFinite(value) || value <= 0) {
      push(t("portfolio.validationInvalidNumber"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      await api.createAlert(coin, direction, value);
      setPrice("");
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

  return (
    <Card title={t("alerts.title")} icon={BellRing} style={{ marginTop: 16 }}>
      <p className="text-sub" style={{ marginTop: 0 }}>{t("alerts.intro")}</p>
      <form className="alert-form" onSubmit={add}>
        <select className="select" value={coin} onChange={(e) => setCoin(e.target.value)} aria-label={t("forecast.coinLabel")}>
          {data.coins.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="select" value={direction} onChange={(e) => setDirection(e.target.value)} aria-label={t("alerts.direction")}>
          <option value="above">{t("alerts.above")}</option>
          <option value="below">{t("alerts.below")}</option>
        </select>
        <input className="input" inputMode="decimal" placeholder={t("alerts.pricePlaceholder")} aria-label={t("alerts.pricePlaceholder")}
               value={price} onChange={(e) => setPrice(e.target.value)} />
        <button className="btn btn-primary btn-sm" type="submit" disabled={busy || full}>{t("alerts.add")}</button>
      </form>
      <p className="text-sub alert-limit">
        {t("alerts.limit", { n: data.active, max: data.max })}
        {full && !user?.premium && <> · <Link to="/premium" className="key-link">{t("alerts.upgrade")}</Link></>}
      </p>
      {data.items.length > 0 && (
        <ul className="alert-list">
          {data.items.map((a) => (
            <li key={a.id} className={a.active ? "" : "alert-done"}>
              <span>
                <strong>{a.coin}</strong> {t(a.direction === "above" ? "alerts.above" : "alerts.below")} {formatPrice(a.target_price)}
                {!a.active && a.triggered_price != null && <span className="text-sub"> · {t("alerts.fired", { price: formatPrice(a.triggered_price) })}</span>}
              </span>
              <button className="btn btn-ghost btn-sm" onClick={() => remove(a.id)} aria-label={t("common.delete")}><Trash2 size={13} /></button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
