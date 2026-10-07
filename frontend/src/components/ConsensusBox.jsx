/** Premium: one weighted verdict from several models (models with a better track record count more). */

import { Crown, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { usePremium } from "../hooks/usePremium";
import { consensusInput } from "../utils/models";

const fmt = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)} %`;

export default function ConsensusBox({ coin, horizon, series }) {
  const { t } = useLanguage();
  const { mode, active } = usePremium();
  const [result, setResult] = useState(null);
  const forecasts = consensusInput(series);
  const signature = JSON.stringify(forecasts);

  useEffect(() => {
    if (!active || forecasts.length < 2) return undefined;
    let alive = true;
    api.consensus(coin, horizon, forecasts).then((r) => alive && setResult(r)).catch(() => alive && setResult(null));
    return () => { alive = false; };
    // signature captures the forecasts; the array itself changes on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, coin, horizon, signature]);

  if (!mode || forecasts.length < 2) return null;
  if (!active) {
    return (
      <div className="consensus consensus-locked">
        <Crown size={15} /> <span>{t("consensus.teaser")}</span> <Link to="/premium" className="key-link">{t("gate.cta")}</Link>
      </div>
    );
  }
  if (!result) return null;
  const up = result.direction === "up";
  return (
    <div className={`consensus consensus-${result.strength}`} data-testid="consensus">
      <Scale size={18} />
      <div>
        <strong>{t(up ? "consensus.up" : "consensus.down", { pct: result.agreement_pct })}</strong>
        <span className="text-sub" style={{ display: "block" }}>
          {t(`consensus.strength_${result.strength}`)} · {t("consensus.median", { value: fmt(result.median_change_pct) })} ·{" "}
          {t("consensus.range", { min: fmt(result.min_change_pct), max: fmt(result.max_change_pct) })}
        </span>
      </div>
    </div>
  );
}
