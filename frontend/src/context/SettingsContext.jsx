import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

const Ctx = createContext(null);

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState({
    restaurant_name: "REST-OS", primary_color: "#C94A29", currency: "IDR",
    tax_rate: 11, service_charge: 5, table_count: 5, logo: "",
  });

  const refresh = useCallback(() => {
    api.get("/settings").then((r) => setSettings(r.data)).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    document.documentElement.style.setProperty("--brand", settings.primary_color || "#C94A29");
  }, [settings.primary_color]);

  return <Ctx.Provider value={{ settings, setSettings, refresh }}>{children}</Ctx.Provider>;
}

export const useSettings = () => useContext(Ctx);
