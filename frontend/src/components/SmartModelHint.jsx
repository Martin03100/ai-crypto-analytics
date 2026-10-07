/** Premium: which model has been most accurate for this coin and horizon, with a one-click switch. */

import { Crown, Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";
import { usePremium } from "../hooks/usePremium";
import { QUANT_LABEL, providerForLabel } from "../utils/models";

export default function SmartModelHint({ coin, horizon, providers, current, onPick }) {
  const { t } = useLanguage();
  const { mode, active } = usePremium();
  const [ranking, setRanking] = useState(null);

  useEffect(() => {
    if (!active) return undefined;
    let alive = true;
    setRanking(null);
    api.modelRanking(coin, horizon).then((r) => alive && setRanking(r)).catch(() => alive && setRanking(null));
    return () => { alive = false; };
  }, [active, coin, horizon]);

  if (!mode) return null;
  if (!active) {
    return (
      <p className="smart-hint smart-hint-locked">
        <Crown size={13} /> {t("smart.teaser")} <Link to="/premium" className="key-link">{t("gate.cta")}</Link>
      </p>
    );
  }
  if (!ranking) return null;
  const top = ranking.ranking[0];
  const match = providerForLabel(ranking.best, providers);
  const name = ranking.best === QUANT_LABEL ? t("provider.quantLabel") : ranking.best;
  const usable = match && match.connected !== false && match.provider !== current;

  return (
    <div className="smart-hint" data-testid="smart-model">
      <Lightbulb size={14} />
      <span>
        {top
          ? t(`smart.best_${ranking.scope}`, { model: name, hit: top.direction_hit_pct, n: top.evaluated, coin })
          : t("smart.noData", { model: name })}
      </span>
      {usable && <button type="button" className="btn btn-ghost btn-sm" onClick={() => onPick(match.provider)}>{t("smart.use")}</button>}
    </div>
  );
}
