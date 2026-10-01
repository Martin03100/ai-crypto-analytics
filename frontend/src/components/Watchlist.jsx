/** Watchlist: the coins the user follows, with live price and 24h change. */

import { Check, Pencil, Star } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useCurrency } from "../context/CurrencyContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { COIN_IDS } from "../utils/coins";

const REFRESH_MS = 60_000;

export default function Watchlist() {
  const { t } = useLanguage();
  const { push } = useToast();
  const { vsCurrency, formatAmount } = useCurrency();
  const [coins, setCoins] = useState(null);
  const [available, setAvailable] = useState([]);
  const [max, setMax] = useState(12);
  const [prices, setPrices] = useState({});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.watchlist()
      .then((r) => { setCoins(r.coins); setAvailable(r.available); setMax(r.max); })
      .catch(() => setCoins([]));
  }, []);

  const loadPrices = useCallback(() => {
    const ids = (coins || []).map((c) => COIN_IDS[c]).filter(Boolean);
    if (ids.length === 0) return;
    api.livePrices(ids, vsCurrency).then((r) => setPrices(r.prices)).catch(() => {});
  }, [coins, vsCurrency]);

  useEffect(() => {
    loadPrices();
    const timer = setInterval(() => { if (document.visibilityState === "visible") loadPrices(); }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [loadPrices]);

  async function toggle(symbol) {
    if (saving) return;                   // one request at a time keeps the server and the UI in step
    const next = coins.includes(symbol) ? coins.filter((c) => c !== symbol) : [...coins, symbol];
    const previous = coins;
    setCoins(next);                       // optimistic: the chip reacts instantly
    setSaving(true);
    try {
      setCoins((await api.setWatchlist(next)).coins);
    } catch (err) {
      setCoins(previous);
      push(err, "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="card watchlist" aria-labelledby="watchlist-title">
      <div className="card-head">
        <h2 id="watchlist-title" className="card-title" style={{ margin: 0 }}><Star size={14} /> {t("watchlist.title")}</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => setEditing((v) => !v)} aria-pressed={editing}>
          {editing ? <><Check size={13} /> {t("common.done")}</> : <><Pencil size={13} /> {t("watchlist.edit")}</>}
        </button>
      </div>

      {editing && (
        <div className="chip-row" role="group" aria-label={t("watchlist.pick")}>
          {available.map((symbol) => {
            const on = coins.includes(symbol);
            return (
              <button key={symbol} type="button" className={`chip ${on ? "on" : ""}`} aria-pressed={on}
                      onClick={() => toggle(symbol)} disabled={saving || (!on && coins.length >= max)}>
                {symbol}
              </button>
            );
          })}
        </div>
      )}

      {coins === null ? (
        <div className="watchlist-grid">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 64 }} />)}</div>
      ) : coins.length === 0 ? (
        <p className="text-sub" style={{ margin: 0 }}>{t("watchlist.empty")}</p>
      ) : (
        <div className="watchlist-grid">
          {coins.map((symbol) => {
            const quote = prices[COIN_IDS[symbol]];
            const price = quote?.[vsCurrency];
            const change = quote?.[`${vsCurrency}_24h_change`];
            const dir = change > 0 ? "up" : change < 0 ? "down" : "";
            return (
              <Link key={symbol} to={`/forecast?coin=${symbol}`} className="watch-tile" title={t("watchlist.forecastFor", { coin: symbol })}>
                <span className="watch-symbol">{symbol}</span>
                <span className="watch-price num">{price != null ? formatAmount(price) : "—"}</span>
                <span className={`watch-change num ${dir}`}>
                  {change != null ? `${change > 0 ? "+" : ""}${change.toFixed(2)} %` : " "}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
