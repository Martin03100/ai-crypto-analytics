import { createContext, useCallback, useContext, useMemo, useState } from "react";

const CurrencyContext = createContext(null);
const STORAGE_KEY = "aca_currency";
export const CURRENCIES = ["USD", "EUR", "CZK", "BTC"];

const SYMBOLS = { USD: "$", EUR: "€", CZK: "Kč", BTC: "₿" };
const LOCALE_MAP = { USD: "en-US", EUR: "sk-SK", CZK: "cs-CZ", BTC: "en-US" };

function loadCurrency() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return CURRENCIES.includes(stored) ? stored : "USD";
}

export function CurrencyProvider({ children }) {
  const [currency, setCurrencyState] = useState(loadCurrency);

  const setCurrency = useCallback((next) => {
    if (!CURRENCIES.includes(next)) return;
    localStorage.setItem(STORAGE_KEY, next);
    setCurrencyState(next);
  }, []);

  /** Formátuje hodnotu v aktuálne zvolenej mene. Pre BTC sa zobrazuje so
   * satoshi presnosťou (8 desatinných miest), pre fiat meny bežné 2. */
  const formatAmount = useCallback((value) => {
    if (value == null || Number.isNaN(value)) return "—";
    if (currency === "BTC") {
      return `${SYMBOLS.BTC}${value.toFixed(value >= 1 ? 4 : 8)}`;
    }
    try {
      return value.toLocaleString(LOCALE_MAP[currency], {
        style: "currency", currency, maximumFractionDigits: value >= 1000 ? 0 : 2,
      });
    } catch {
      return `${SYMBOLS[currency] || ""}${value.toFixed(2)}`;
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
