import React from "react";
import { useI18n, LANGS } from "@/i18n";

export const LangSwitch = ({ dark = false }) => {
  const { lang, setLang } = useI18n();
  return (
    <div data-testid="lang-switch" className={`flex items-center gap-1 rounded-full p-1 ${dark ? "bg-white/10" : "bg-black/5"}`}>
      {LANGS.map((l) => (
        <button
          key={l.code}
          data-testid={`lang-${l.code}`}
          onClick={() => setLang(l.code)}
          className={`px-2.5 py-1 text-xs font-medium rounded-full transition-colors duration-200 ${
            lang === l.code ? "brand-bg text-white" : dark ? "text-white/70" : "text-neutral-600"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
};

const KEYS = ["new", "accepted", "preparing", "ready", "delivered", "closed"];

export const StatusTracker = ({ status }) => {
  const { t } = useI18n();
  const idx = KEYS.indexOf(status);
  return (
    <div data-testid="status-tracker" className="flex items-center gap-1.5">
      {KEYS.map((k, i) => (
        <div key={k} className="flex-1">
          <div
            className={`h-1.5 rounded-full transition-all duration-500 ${i <= idx ? "brand-bg" : "bg-neutral-200"}`}
          />
          <div className={`mt-1.5 text-[10px] font-medium truncate ${i <= idx ? "text-neutral-900" : "text-neutral-400"}`}>
            {t(`status_${k}`)}
          </div>
        </div>
      ))}
    </div>
  );
};

export const StatusBadge = ({ status }) => {
  const { t } = useI18n();
  const map = {
    new: "bg-[#C94A29] text-white",
    accepted: "bg-amber-100 text-amber-800",
    preparing: "bg-amber-500 text-white",
    ready: "bg-[#2E3D36] text-white",
    delivered: "bg-emerald-100 text-emerald-800",
    closed: "bg-neutral-200 text-neutral-700",
  };
  return (
    <span data-testid={`status-badge-${status}`} className={`px-2.5 py-1 rounded-full text-xs font-bold ${map[status]}`}>
      {t(`status_${status}`)}
    </span>
  );
};
