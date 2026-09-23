import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "./AuthContext";

const ProvidersContext = createContext(null);

/** Nacita zoznam AI providerov (Gemini/OpenAI/Anthropic/DeepSeek/Grok) a ich
 * stav pripojenia RAZ, zdiela ho medzi Forecast/Portfolio/Chat/Account/DailyDigest
 * namiesto toho, aby si kazda stranka volala /account/api-keys nezavisle. */
export function ProvidersProvider({ children }) {
  const { user } = useAuth();
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!user) return;
    setLoading(true);
    api.listApiKeys().then(setProviders).catch(() => {}).finally(() => setLoading(false));
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const connected = useMemo(() => providers.filter((p) => p.connected), [providers]);
  const defaultProvider = connected[0]?.provider || null;

  const value = useMemo(
    () => ({ providers, connected, defaultProvider, loading, refresh }),
    [providers, connected, defaultProvider, loading, refresh]
  );

  return <ProvidersContext.Provider value={value}>{children}</ProvidersContext.Provider>;
}

export function useProviders() {
  const ctx = useContext(ProvidersContext);
  if (!ctx) throw new Error("useProviders musi byt pouzity vnutri ProvidersProvider");
  return ctx;
}
