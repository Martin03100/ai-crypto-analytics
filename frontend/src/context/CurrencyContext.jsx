/** Display currency context. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";

const CurrencyContext = createContext(null);
const STORAGE_KEY = "aca_currency";
export const CURRENCIES = ["USD", "EUR", "CZK", "BTC"];

const SYMBOLS = { USD: "$", EUR: "€", CZK: "Kč", BTC: "₿" };
const LOCALE_MAP = { USD: "en-US", EUR: "sk-SK", CZK: "cs-CZ", BTC: "en-US" };

function loadCurrency() {
  let stored = null;
  try { stored = localStorage.getItem(STORAGE_KEY); } catch { /* storage blocked */ }
  return CURRENCIES.includes(stored) ? stored : "USD";
}

export function CurrencyProvider({ children }) {
  const [currency, setCurrencyState] = useState(loadCurrency);

  const setCurrency = useCallback((next) => {
    if (!CURRENCIES.includes(next)) return;
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* storage blocked */ }
    setCurrencyState(next);
  }, []);

  const formatAmount = useCallback((value, decimals) => {
    if (value == null || Number.isNaN(value)) return "—";
    if (currency === "BTC") {
      return `${SYMBOLS.BTC}${value.toFixed(decimals ?? (value >= 1 ? 4 : 8))}`;
    }
    const abs = Math.abs(value);
    const digits = decimals ?? (abs >= 1000 ? 0 : abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6);
    try {
      return value.toLocaleString(LOCALE_MAP[currency], {
        style: "currency", currency, minimumFractionDigits: digits, maximumFractionDigits: digits,
      });
    } catch {
      return `${SYMBOLS[currency] || ""}${value.toFixed(digits)}`;
    }
  }, [currency]);

  const value = useMemo(
    () => ({ currency, setCurrency, formatAmount, vsCurrency: currency.toLowerCase() }),
    [currency, setCurrency, formatAmount]
  );

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency() {
  const ctx = useContext(CurrencyContext);
  if (!ctx) throw new Error("useCurrency musi byt pouzity vnutri CurrencyProvider");
  return ctx;
}
