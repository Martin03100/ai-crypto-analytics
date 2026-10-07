/** Free card: what derivatives, options, capital flows, macro and regulators say right now, for one coin. */

import { Activity, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { COINS } from "../utils/coins";
import { signalBalance } from "../utils/signals";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import SignalList from "./SignalList";
import { SkeletonLines } from "./Skeleton";

export default function MarketSignals({ initialCoin = "BTC", compact = false, style }) {
  const { t } = useLanguage();
  const [coin, setCoin] = useState(initialCoin);
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    setFailed(false);
    setData(null);
    api.marketSignals(coin).then(setData).catch(() => setFailed(true));
  }, [coin]);
  useEffect(load, [load]);

  const balance = signalBalance(data?.items);
  const total = balance.bullish + balance.bearish;
  const items = compact ? (data?.items || []).filter((s) => s.tone !== "neutral").slice(0, 8) : data?.items;

  return (
    <Card title={<>{t("signals.title")} <InfoTip text={t("signals.help")} /></>} icon={Activity} style={style}>
      <div className="signals-head">
        <select className="select signals-coin" value={coin} onChange={(e) => setCoin(e.target.value)} aria-label={t("forecast.coinLabel")}>
          {COINS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {total > 0 && (
          <div className="signals-balance" aria-label={t("signals.balanceLabel")}>
            <span className="up">▲ {balance.bullish}</span>
            <div className="signals-bar"><span style={{ width: `${(balance.bullish / total) * 100}%` }} /></div>
            <span className="down">{balance.bearish} ▼</span>
          </div>
        )}
      </div>
      {failed ? (
        <p className="text-sub">{t("signals.failed")} <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={13} /> {t("common.retry")}</button></p>
      ) : !data ? <SkeletonLines count={4} /> : data.items.length === 0 ? (
        <p className="text-sub">{t("signals.empty")}</p>
      ) : (
        <>
          <SignalList items={items} compact={compact} />
          {compact && data.items.length > items.length && <Link to="/market" className="key-link signals-more">{t("signals.more", { n: data.items.length - items.length })}</Link>}
        </>
      )}
      <p className="text-sub scanner-note">{t("signals.note")}</p>
    </Card>
  );
}
