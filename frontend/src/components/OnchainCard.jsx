import { Waves } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "./Card";
import InfoTip from "./InfoTip";
import { useLanguage } from "../context/LanguageContext";
import { localeForLang } from "../i18n/locale";

/** Velryby a on-chain aktivita (BTC, ETH, DOGE) z Blockchair. */
export default function OnchainCard() {
  const { t, lang } = useLanguage();
  const [items, setItems] = useState(null);
  useEffect(() => {
    api.onchain().then((res) => setItems(res.items || [])).catch(() => setItems([]));
  }, []);
  const locale = localeForLang(lang);
  const usd = (v) => `$${(v / 1e6).toLocaleString(locale, { maximumFractionDigits: 1 })}M`;

  return (
    <Card title={<>{t("onchain.title")} <InfoTip text={t("help.whales")} /></>} icon={Waves} style={{ marginBottom: 16 }}>
      {items === null && <p className="text-sub">{t("onchain.loading")}</p>}
      {items && items.length === 0 && <p className="text-sub">{t("onchain.empty")}</p>}
      {items && items.length > 0 && (
        <div className="grid grid-3">
          {items.map((it) => (
            <div key={it.coin} className="onchain-item">
              <strong>{it.coin}</strong>
              {it.transactions_24h != null && <p className="text-sub">{t("onchain.tx24h", { n: it.transactions_24h.toLocaleString(locale) })}</p>}
              {it.whale_count ? (
                <p className="text-sub">{t("onchain.whales", {
                  count: it.whale_count, threshold: usd(it.whale_threshold_usd), total: usd(it.whale_total_usd),
                  max: usd(it.whale_max_usd), hours: it.whale_span_hours ?? "?",
                })}</p>
              ) : <p className="text-sub">{t("onchain.noWhales")}</p>}
            </div>
          ))}
        </div>
      )}
      <p className="data-sources">{t("onchain.source")}</p>
    </Card>
  );
}
