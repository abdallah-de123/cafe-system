// Auth state: current user, login/logout, change password. Token stored in localStorage.
import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

const AuthCtx = createContext(null);

// Where a role lands after login. Owner and super admin share the management dashboard.
export const homeFor = (role) => (role === "cashier" ? "/cashier" : "/owner");

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("restos_token");
    if (!token) return setLoading(false);
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem("restos_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("restos_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (_) {}
    localStorage.removeItem("restos_token");
    setUser(null);
  };

  // Changing the password revokes old sessions; the server hands back a fresh token.
  const changePassword = async (current_password, new_password) => {
    const { data } = await api.post("/auth/change-password", { current_password, new_password });
    localStorage.setItem("restos_token", data.token);
    setUser(data.user);
  };

  return <AuthCtx.Provider value={{ user, loading, login, logout, changePassword }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
