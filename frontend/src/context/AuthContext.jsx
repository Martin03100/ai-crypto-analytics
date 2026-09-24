import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  // Prihlasenie zije v HttpOnly cookie, nie v localStorage. Pri nacitani
  // appky preto overime session cez /auth/me namiesto citania tokenu.
  useEffect(() => {
    api.me()
      .then((res) => setUser({ username: res.username, id: res.user_id, email: res.email }))
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await api.login(username, password);
    setUser({ username: res.username, id: res.user_id, email: res.email });
    return res;
  }, []);

  const register = useCallback(async (username, password, email) => {
    const res = await api.register(username, password, email);
    setUser({ username: res.username, id: res.user_id, email: res.email });
    return res;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const updateEmail = useCallback((email) => {
    setUser((prev) => (prev ? { ...prev, email } : prev));
  }, []);

  const value = useMemo(
    () => ({ user, checking, login, register, logout, updateEmail }),
    [user, checking, login, register, logout, updateEmail]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth musi byt pouzity vnutri AuthProvider");
  return ctx;
}
