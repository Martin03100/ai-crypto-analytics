import { useEffect, useState } from "react";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";

/** Debounced vyhladavanie ktorejkolvek mincy na CoinGecko (custom mince v
 * Portfolio Advisor). Vytiahnute z Portfolio.jsx pre lepsiu citatelnost. */
export default function CoinSearchPicker({ onPick }) {
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await api.searchCoins(query.trim());
        setResults(res.results || []);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="coin-search-wrap field">
      <label>{t("coinPicker.label")}</label>
      <input
        className="input"
        placeholder={t("coinPicker.placeholder")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="coin-search-results">
          {results.map((c) => (
            <div
              key={c.id}
              className="coin-search-item"
              onClick={() => {
                onPick(c);
                setQuery("");
                setResults([]);
                setOpen(false);
              }}
            >
              <span>{c.name}</span>
              <span className="text-sub mono">{c.symbol}</span>
            </div>
          ))}
        </div>
      )}
      {searching && <p className="text-sub" style={{ marginTop: 4 }}>{t("common.searching")}</p>}
    </div>
  );
}
