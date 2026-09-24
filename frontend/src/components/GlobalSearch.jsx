import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useLanguage } from "../context/LanguageContext";

export default function GlobalSearch() {
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const navigate = useNavigate();
  const wrapRef = useRef(null);

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
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function goToCoin(coin) {
    setQuery("");
    setResults([]);
    setOpen(false);
    navigate(`/forecast?coin=${encodeURIComponent(coin.symbol)}`);
  }

  return (
    <div className="global-search" ref={wrapRef}>
      <Search size={15} className="global-search-icon" />
      <input
        className="global-search-input"
        placeholder={t("search.placeholder")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {query && (
        <button className="global-search-clear" onClick={() => { setQuery(""); setResults([]); }} aria-label={t("common.clearSearch")}>
          <X size={13} />
        </button>
      )}
      {open && (searching || results.length > 0) && (
        <div className="coin-search-results global-search-results">
          {searching && <div className="coin-search-item text-sub">{t("common.searching")}</div>}
          {!searching && results.map((c) => (
            <button key={c.id} type="button" className="coin-search-item" onClick={() => goToCoin(c)}>
              <span>{c.name}</span>
              <span className="text-sub mono">{c.symbol}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
