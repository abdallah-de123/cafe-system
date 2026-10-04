import React from "react";
import { Link } from "react-router-dom";
import { QrCode, ChefHat, LayoutDashboard, ArrowRight } from "lucide-react";
import { useSettings } from "@/context/SettingsContext";
import { LangSwitch } from "@/components/Shared";
import { useI18n } from "@/i18n";

export default function Landing() {
  const { settings } = useSettings();
  const { t } = useI18n();
  const tables = Array.from({ length: settings.table_count || 5 }, (_, i) => i + 1);

  return (
    <div className="min-h-screen bg-[#F8F7F4]">
      <header className="glass sticky top-0 z-20 border-b border-black/5">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl brand-bg grid place-items-center">
              <ChefHat className="w-5 h-5 text-white" />
            </div>
            <span className="font-display font-bold text-lg">{settings.restaurant_name}</span>
          </div>
          <div className="flex items-center gap-3">
            <LangSwitch />
            <Link data-testid="landing-login-link" to="/login" className="text-sm font-medium brand-text hover:underline">
              {t("login")}
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-16">
        <p className="text-xs font-bold tracking-[0.2em] uppercase brand-text mb-4">Restaurant Operating System</p>
        <h1 className="font-display text-4xl sm:text-5xl font-black leading-none max-w-2xl">
          {t("scanTitle")} — tanpa aplikasi, tanpa menunggu.
        </h1>
        <p className="text-base text-neutral-600 mt-6 max-w-xl">
          Pindai QR di meja, pesan langsung dari ponsel, dan pantau statusnya secara real-time.
        </p>

        <div className="mt-14 grid gap-8 md:grid-cols-2">
          <section className="bg-white rounded-2xl border border-neutral-200 soft-shadow p-7">
            <div className="flex items-center gap-2 mb-1">
              <QrCode className="w-5 h-5 brand-text" />
              <h2 className="font-display font-bold text-lg">Demo Meja (QR)</h2>
            </div>
            <p className="text-sm text-neutral-500 mb-5">Buka salah satu meja seperti pelanggan yang memindai QR.</p>
            <div className="flex flex-wrap gap-3">
              {tables.map((n) => (
                <Link
                  key={n}
                  data-testid={`landing-table-${n}`}
                  to={`/t/${n}`}
                  className="px-5 py-3 rounded-xl bg-[#F8F7F4] border border-neutral-200 font-display font-bold hover:-translate-y-1 hover:border-[color:var(--brand)] transition-transform duration-300"
                >
                  {t("table")} {n}
                </Link>
              ))}
            </div>
          </section>

          <section className="bg-[#2E3D36] text-white rounded-2xl p-7">
            <div className="flex items-center gap-2 mb-1">
              <LayoutDashboard className="w-5 h-5" />
              <h2 className="font-display font-bold text-lg">Dasbor Staf</h2>
            </div>
            <p className="text-sm text-white/70 mb-5">Kasir & pemilik masuk untuk mengelola pesanan real-time.</p>
            <Link
              data-testid="landing-staff-login"
              to="/login"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl brand-bg font-medium active:scale-95 transition-transform duration-200"
            >
              {t("login")} <ArrowRight className="w-4 h-4" />
            </Link>
            <div className="mt-6 text-xs text-white/60 space-y-1 font-mono">
              <div>owner@restos.id / owner123</div>
              <div>kasir1@restos.id / kasir123</div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
