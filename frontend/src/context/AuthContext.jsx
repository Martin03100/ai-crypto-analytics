/** Authentication context. */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, isTransient, SESSION_EXPIRED_EVENT } from "../api";
import { clearOfflineData, offlineSessionUser, rememberOfflineSession } from "../pwa";
import { getReferralCode } from "../utils/referral";
import { useLanguage } from "./LanguageContext";

const AuthContext = createContext(null);

function toUser(res) {
  return {
    username: res.username, id: res.user_id, email: res.email,
    emailVerified: res.email_verified, totpEnabled: Boolean(res.totp_enabled), premium: Boolean(res.premium),
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  const { lang } = useLanguage();

  useEffect(() => {   // emails are sent in the language the user last used in the app
    if (user?.id) api.setPreferences({ lang }).catch(() => {});
  }, [lang, user?.id]);

  useEffect(() => {
    api.me()
      .then((res) => {
        const next = res.user_id ? toUser(res) : null;
        if (next) rememberOfflineSession(next);
        setUser(next);
      })
      .catch((err) => {
        // Server unreachable (offline, cold start, proxy 502-504): reuse the account confirmed online in the last 24 h, so the
        // installed app opens with its cached data. A rejected session (401) or an expired window signs out.
        const offlineUser = isTransient(err) ? offlineSessionUser() : null;
        if (!offlineUser) clearOfflineData();
        setUser(offlineUser);
      })
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    function onExpired() {
      clearOfflineData();
      setUser((prev) => {
        if (prev) {
          try { sessionStorage.setItem("aca_session_expired", "1"); } catch {  }
        }
        return null;
      });
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const login = useCallback(async (username, password, totpCode) => {
    const res = await api.login(username, password, totpCode);
    await clearOfflineData();   // never show another account's cached data
    rememberOfflineSession(toUser(res));
    setUser(toUser(res));
    return res;
  }, []);

  const register = useCallback(async (username, password, email, captchaToken) => {
    const res = await api.register(username, password, email, captchaToken, getReferralCode());
    await clearOfflineData();
    rememberOfflineSession(toUser(res));
    setUser(toUser(res));
    return res;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // The local session is cleared either way; a failed logout request must not surface as an error.
    } finally {
      await clearOfflineData();
      setUser(null);
    }
  }, []);

  const updateEmail = useCallback((email, extra = {}) => {
    setUser((prev) => (prev ? { ...prev, email, ...extra } : prev));
  }, []);

  const patchUser = useCallback((fields) => {
    setUser((prev) => (prev ? { ...prev, ...fields } : prev));
  }, []);

  const value = useMemo(
    () => ({ user, checking, login, register, logout, updateEmail, patchUser }),
    [user, checking, login, register, logout, updateEmail, patchUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth musi byt pouzity vnutri AuthProvider");
  return ctx;
}
