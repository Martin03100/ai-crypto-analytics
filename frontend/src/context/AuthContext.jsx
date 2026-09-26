import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

/** Odpoved servera -> objekt pouzivatela v appke. */
function toUser(res) {
  return {
    username: res.username, id: res.user_id, email: res.email,
    emailVerified: res.email_verified, totpEnabled: Boolean(res.totp_enabled),
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  // Prihlasenie zije v HttpOnly cookie, nie v localStorage. Pri nacitani
  // appky preto overime session cez /auth/me namiesto citania tokenu.
  useEffect(() => {
    api.me()
      .then((res) => setUser(toUser(res)))
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (username, password, totpCode) => {
    const res = await api.login(username, password, totpCode);
    setUser(toUser(res));
    return res;
  }, []);

  const register = useCallback(async (username, password, email, captchaToken) => {
    const res = await api.register(username, password, email, captchaToken);
    setUser(toUser(res));
    return res;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
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
