/** AI providers context. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "./AuthContext";

const ProvidersContext = createContext(null);

export function ProvidersProvider({ children }) {
  const { user } = useAuth();
  const userId = user?.id;
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    if (!userId) {
      setProviders([]);
      return;
    }
    setLoading(true);
    api.listApiKeys()
      .then((res) => setProviders(Array.isArray(res) ? res.filter((p) => p && typeof p.provider === "string") : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

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
