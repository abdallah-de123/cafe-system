import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const api = axios.create({ baseURL: `${BACKEND_URL}/api` });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("restos_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return e?.message || "Terjadi kesalahan";
}

export function money(v, currency = "IDR") {
  const n = Number(v || 0);
  if (currency === "IDR") return "Rp " + n.toLocaleString("id-ID");
  if (currency === "SAR") return n.toLocaleString() + " SAR";
  return currency + " " + n.toLocaleString();
}
