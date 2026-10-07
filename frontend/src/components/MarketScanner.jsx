/** Market scanner: expected 24h move, RSI and a plain signal for every supported coin. Free users see the top 5. */

import { Lock, Radar, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { usePremium } from "../hooks/usePremium";
import { formatPrice } from "../utils/formatPrice";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { SkeletonLines } from "./Skeleton";

const SORTS = { expected: (r) => -Math.abs(r.expected_24h_pct ?? 0), up: (r) => -(r.expected_24h_pct ?? -99),
  down: (r) => r.expected_24h_pct ?? 99, rsi: (r) => -(r.rsi ?? -1) };

function Pct({ value }) {
  if (value == null) return <span className="text-sub">—</span>;
  return <span className={`mono ${value > 0 ? "up" : value < 0 ? "down" : ""}`}>{value > 0 ? "+" : ""}{value.toFixed(2)} %</span>;
}

export default function MarketScanner() {
  const { t } = useLanguage();
  const { mode } = usePremium();
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);
  const [sort, setSort] = useState("expected");

  const load = useCallback(() => {
    setFailed(false);
    api.scanner().then(setData).catch(() => setFailed(true));
  }, []);
  useEffect(() => { load(); }, [load]);

  const rows = data ? [...data.rows].sort((a, b) => SORTS[sort](a) - SORTS[sort](b)) : [];

  return (
    <Card title={<>{t("scanner.title")} <InfoTip text={t("scanner.help")} /></>} icon={Radar} style={{ marginBottom: 16 }}>
      <div className="scanner-head">
        <p className="text-sub" style={{ margin: 0 }}>{t("scanner.intro")}</p>
        <div className="tabs" role="group" aria-label={t("scanner.sort")}>
          {Object.keys(SORTS).map((k) => (
            <button key={k} type="button" className={`tab ${sort === k ? "active" : ""}`} onClick={() => setSort(k)}>{t(`scanner.sort_${k}`)}</button>
          ))}
        </div>
      </div>
      {failed ? (
        <p className="text-sub">{t("scanner.failed")} <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /> {t("common.retry")}</button></p>
      ) : !data ? <SkeletonLines count={5} /> : rows.length === 0 ? (
        <p className="text-sub">{t("scanner.empty")} <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /> {t("common.retry")}</button></p>
      ) : (
        <div className="table-scroll">
          <table className="lb-table scanner-table">
            <thead>
              <tr><th>{t("scanner.colCoin")}</th><th>{t("scanner.colPrice")}</th><th>24h</th><th>7d</th>
                <th>{t("scanner.colExpected")}</th><th>RSI</th><th>{t("scanner.colSignal")}</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.coin}>
                  <td><strong>{r.coin}</strong></td>
                  <td className="mono">{formatPrice(r.price)}</td>
                  <td><Pct value={r.change_24h} /></td>
                  <td><Pct value={r.change_7d} /></td>
                  <td><Pct value={r.expected_24h_pct} />{r.range_pct != null && <span className="text-sub scanner-range"> ±{(r.range_pct / 2).toFixed(1)} %</span>}</td>
                  <td className="mono">{r.rsi ?? "—"}</td>
                  <td><span className={`signal signal-${r.signal}`}>{t(`scanner.signal_${r.signal}`)}</span></td>
                </tr>
              ))}
              {mode && data.locked > 0 && (
                <tr className="scanner-locked">
                  <td colSpan={7}>
                    <Lock size={13} /> {t("scanner.locked", { n: data.locked })} <Link to="/premium" className="key-link">{t("gate.cta")}</Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-sub scanner-note">{t("scanner.note")}</p>
    </Card>
  );
}
