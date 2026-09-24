import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useProviders } from "../context/ProvidersContext";
import { useLanguage } from "../context/LanguageContext";

const STORAGE_KEY = "aca_daily_digest";

function todayKey() {
  return new Date().toISOString().slice(0, 10); // YYYY-MM-DD
}

function loadCached() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed.date === todayKey() ? parsed : null;
  } catch {
    return null;
  }
}

export default function DailyDigest() {
  const { t } = useLanguage();
  const { defaultProvider, loading: providersLoading } = useProviders();
  const [digest, setDigest] = useState(null);
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem("aca_digest_dismissed") === "1");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (dismissed || providersLoading) return;
    const cached = loadCached();
    // Cachovany MOCK vysledok berieme ako platny iba ak pouzivatel STALE
    // nema pripojeny ziaden AI provider. Inak by prehlad ostal "zaseknuty"
    // v mock rezime cely den aj po tom, co si niekto medzitym pripoji
    // skutocny API kluc (presne toto predtym robilo dojem, ze appka
    // "ignoruje" novo pripojeny kluc).
    const cacheIsStale = Boolean(cached?.isMock && defaultProvider);
    if (cached && !cacheIsStale) {
      setDigest(cached);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const provider = defaultProvider || "gemini";
    api.dailyDigest(provider)
      .then((res) => {
        if (cancelled || !res.data) return;
        const payload = { date: todayKey(), data: res.data, isMock: res.is_mock };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        setDigest(payload);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providersLoading, defaultProvider, dismissed]);

  function dismiss() {
    setDismissed(true);
    sessionStorage.setItem("aca_digest_dismissed", "1");
  }

  if (dismissed || (!digest && !loading)) return null;

  return (
    <div className="daily-digest">
      <div className="daily-digest-icon"><Sparkles size={16} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="daily-digest-title">
          {t("digest.title")} {digest?.isMock && <span className="badge badge-mock" style={{ marginLeft: 6 }}>{t("badge.mock")}</span>}
        </div>
        {loading && !digest && <p className="text-sub" style={{ margin: "4px 0 0" }}>{t("digest.preparing")}</p>}
        {digest && (
          <>
            <p style={{ margin: "4px 0 6px", fontSize: 13, color: "var(--text-secondary)" }}>{digest.data.zhrnutie}</p>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--text-tertiary)" }}>
              {digest.data.kluceve_body?.map((point, i) => <li key={i}>{point}</li>)}
            </ul>
          </>
        )}
      </div>
      <button className="btn btn-ghost btn-sm" onClick={dismiss} title={t("digest.hide")} aria-label={t("digest.hide")}><X size={14} /></button>
    </div>
  );
}
