import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ChefHat, Loader2 } from "lucide-react";
import { useAuth, homeFor } from "@/context/AuthContext";
import { useI18n } from "@/i18n";
import { errMsg } from "@/lib/api";
import { LangSwitch } from "@/components/Shared";

export default function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const u = await login(email, password);
      nav(homeFor(u.role), { replace: true });
    } catch (e2) {
      setErr(errMsg(e2));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2">
      <div className="hidden md:flex flex-col justify-between bg-[#2E3D36] text-white p-12">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl brand-bg grid place-items-center">
            <ChefHat className="w-5 h-5" />
          </div>
          <span className="font-display font-bold text-lg">REST-OS</span>
        </div>
        <div>
          <h1 className="font-display text-4xl font-black leading-none">Kelola layanan Anda dalam satu layar.</h1>
          <p className="text-white/70 mt-5 text-sm max-w-sm">
            Pesanan masuk real-time, alur dapur yang ketat, dan laporan penjualan otomatis.
          </p>
        </div>
        <div className="text-xs text-white/50">REST-OS</div>
      </div>

      <div className="flex flex-col justify-center px-6 sm:px-16 py-14 bg-[#F8F7F4]">
        <div className="flex justify-between items-center mb-10">
          <Link to="/" className="text-sm text-neutral-500 hover:underline">← REST-OS</Link>
          <LangSwitch />
        </div>
        <h2 className="font-display text-3xl font-bold mb-8">{t("login")}</h2>
        <form onSubmit={submit} className="space-y-4 max-w-sm">
          <div>
            <label className="text-sm font-medium text-neutral-600">{t("email")}</label>
            <input
              data-testid="login-email-input"
              type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full h-12 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] transition-colors"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-neutral-600">{t("password")}</label>
            <input
              data-testid="login-password-input"
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 w-full h-12 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] transition-colors"
            />
          </div>
          {err && <p data-testid="login-error" className="text-sm text-red-600">{err}</p>}
          <button
            data-testid="login-submit-btn" type="submit" disabled={busy}
            className="w-full h-12 rounded-xl brand-bg text-white font-medium active:scale-95 transition-transform duration-200 flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {busy && <Loader2 className="w-4 h-4 animate-spin" />} {t("login")}
          </button>
        </form>
      </div>
    </div>
  );
}
