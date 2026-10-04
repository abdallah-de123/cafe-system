// Small shared UI pieces: language switcher, order status widgets, change-password dialog.
import React, { useState } from "react";
import { toast } from "sonner";
import { KeyRound } from "lucide-react";
import { useI18n, LANGS } from "@/i18n";
import { useSettings } from "@/context/SettingsContext";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";

// Language pills. `onlyEnabled` (customer screens) hides languages the restaurant disabled.
export const LangSwitch = ({ dark = false, onlyEnabled = false }) => {
  const { lang, setLang } = useI18n();
  const { settings } = useSettings();
  const enabled = settings.enabled_languages || ["id", "en", "ar"];
  const list = onlyEnabled ? LANGS.filter((l) => enabled.includes(l.code)) : LANGS;
  if (onlyEnabled && list.length < 2) return null;
  return (
    <div data-testid="lang-switch" className={`flex items-center gap-1 rounded-full p-1 ${dark ? "bg-white/10" : "bg-black/5"}`}>
      {list.map((l) => (
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
          <div className={`h-1.5 rounded-full transition-all duration-500 ${i <= idx ? "brand-bg" : "bg-neutral-200"}`} />
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

const field = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

// Button + modal that lets any signed-in user change their own password.
export const ChangePasswordButton = ({ dark = false }) => {
  const { t } = useI18n();
  const { changePassword } = useAuth();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ cur: "", nw: "", rep: "" });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (f.nw !== f.rep) return toast.error(t("passwordMismatch"));
    setBusy(true);
    try {
      await changePassword(f.cur, f.nw);
      toast.success(t("passwordChanged"));
      setOpen(false); setF({ cur: "", nw: "", rep: "" });
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <>
      <button data-testid="change-password-btn" onClick={() => setOpen(true)} title={t("changePassword")}
        className={`w-11 h-11 rounded-xl grid place-items-center ${dark ? "bg-white/10 text-white" : "bg-black/5"}`}>
        <KeyRound className="w-4 h-4" />
      </button>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4" onClick={() => setOpen(false)}>
          <div data-testid="change-password-modal" className="bg-white rounded-2xl p-6 w-full max-w-sm text-neutral-900" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display font-bold text-xl mb-4">{t("changePassword")}</h3>
            <div className="space-y-3">
              <input data-testid="cp-current-input" type="password" className={field} placeholder={t("currentPassword")} value={f.cur} onChange={(e) => setF({ ...f, cur: e.target.value })} />
              <input data-testid="cp-new-input" type="password" className={field} placeholder={t("newPassword")} value={f.nw} onChange={(e) => setF({ ...f, nw: e.target.value })} />
              <input data-testid="cp-repeat-input" type="password" className={field} placeholder={t("confirmPassword")} value={f.rep} onChange={(e) => setF({ ...f, rep: e.target.value })} />
            </div>
            <div className="mt-5 flex gap-3">
              <button data-testid="cp-cancel-btn" onClick={() => setOpen(false)} className="flex-1 h-12 rounded-xl border border-neutral-200 font-medium">{t("cancel")}</button>
              <button data-testid="cp-save-btn" onClick={submit} disabled={busy} className="flex-1 h-12 rounded-xl brand-bg text-white font-medium disabled:opacity-60">{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
