/** Feature switches and the announcement the admin controls (GET /public/config). */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";

const DEFAULTS = {
  signups_enabled: true, chat_enabled: true, compare_enabled: true, backtest_enabled: true, tipsters_enabled: true,
  waitlist_enabled: false, digest_enabled: true, referrals_enabled: true, announcement: "", announcement_level: "info",
  operator_name: "", operator_business_id: "", operator_address: "",
  premium: null, loaded: false,
};

const AppConfigContext = createContext({ ...DEFAULTS, reload: () => {} });

export function AppConfigProvider({ children }) {
  const [config, setConfig] = useState(DEFAULTS);
  const reload = useCallback(() => api.publicConfig()
    .then((c) => setConfig({ ...DEFAULTS, ...c, loaded: true }))
    .catch(() => setConfig((prev) => ({ ...prev, loaded: true }))), []);
  useEffect(() => { reload(); }, [reload]);
  const value = useMemo(() => ({ ...config, reload }), [config, reload]);
  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  return useContext(AppConfigContext);
}
