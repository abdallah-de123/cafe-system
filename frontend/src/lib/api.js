// Axios client + helpers. The JWT lives in localStorage and is attached to every request.
import axios from "axios";
import { errText } from "@/i18n";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("restos_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Turn any API error into a translated, human-readable message.
export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (d && typeof d === "object" && !Array.isArray(d) && d.code) return errText(d.code, d);
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return e?.message || errText("UNKNOWN");
}

// Format money for the active currency.
export function money(v, currency = "IDR") {
  const n = Number(v || 0);
  if (currency === "IDR") return "Rp " + n.toLocaleString("id-ID");
  if (currency === "SAR") return n.toLocaleString() + " SAR";
  return currency + " " + n.toLocaleString();
}
