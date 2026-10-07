/** Weekly "Beat the AI": guess one coin's price for the end of the week, the closest guess wins a badge. */

import { Trophy } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { useToast } from "../context/ToastContext";
import { localeForLang } from "../i18n/locale";
import { formatPrice } from "../utils/formatPrice";
import { Card } from "./Card";

export default function ChallengeCard({ style }) {
  const { t, lang } = useLanguage();
  const { user } = useAuth();
  const { push } = useToast();
  const [data, setData] = useState(null);
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    (user ? api.challenge() : api.publicChallenge()).then(setData).catch(() => setData(null));
  }, [user]);
  useEffect(load, [load]);

  if (!data || (!data.current && !data.last)) return null;
  const cur = data.current;
  const locale = localeForLang(lang);
  const when = (iso) => new Date(iso).toLocaleString(locale, { weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });

  const submit = async (e) => {
    e.preventDefault();
    const value = Number(String(price).replace(/\s/g, "").replace(",", "."));
    if (!(value > 0)) {
      push(t("portfolio.validationInvalidNumber"), "error", { translated: true });
      return;
    }
    setBusy(true);
    try {
      setData(await api.enterChallenge(value));
      push(t("weekly.saved"), "success", { translated: true });
    } catch (err) {
      push(err?.message || "error", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={t("weekly.title")} icon={Trophy} style={style} className="challenge-card">
      {cur && (
        <>
          <p className="challenge-lead">{t("weekly.lead", { coin: cur.coin })}</p>
          <div className="challenge-facts">
            <div><span className="text-sub">{t("weekly.start")}</span><strong className="mono">{formatPrice(cur.start_price)}</strong></div>
            {cur.ai_price != null && <div><span className="text-sub">{t("weekly.ai")}</span><strong className="mono">{formatPrice(cur.ai_price)}</strong></div>}
            <div><span className="text-sub">{cur.open ? t("weekly.closes") : t("weekly.ends")}</span><strong>{when(cur.open ? cur.deadline : cur.ends_at)}</strong></div>
            <div><span className="text-sub">{t("weekly.players")}</span><strong>{cur.entries}</strong></div>
          </div>
          {!user ? (
            <Link to="/auth?tab=register" className="btn btn-primary btn-sm">{t("weekly.join")}</Link>
          ) : cur.my_price != null ? (
            <p className="text-sub">{t("weekly.yourTip", { price: formatPrice(cur.my_price) })}</p>
          ) : cur.open ? (
            <form className="challenge-form" onSubmit={submit}>
              <input className="input" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)}
                     placeholder={t("weekly.placeholder", { coin: cur.coin })} aria-label={t("weekly.placeholder", { coin: cur.coin })} />
              <button className="btn btn-primary btn-sm" type="submit" disabled={busy}>{t("weekly.submit")}</button>
            </form>
          ) : <p className="text-sub">{t("weekly.closed")}</p>}
        </>
      )}
      {data.last && (
        <p className="text-sub challenge-last">
          {t("weekly.last", { coin: data.last.coin, price: formatPrice(data.last.end_price) })}{" "}
          {data.last.winner
            ? t("weekly.winner", { name: data.last.winner, err: data.last.winner_error_pct, ai: data.last.ai_error_pct ?? "—" })
            : t("weekly.noWinner")}
          {data.last.entries > 0 && <> {t("weekly.beatAi", { n: data.last.beat_ai, total: data.last.entries })}</>}
          {data.last.you_won && <strong> {t("weekly.youWon")}</strong>}
        </p>
      )}
    </Card>
  );
}
