// Settings screen grouped into sections (General, Time & Language, Money, Orders, Inventory, Security).
// Every field maps 1:1 to a backend setting key; the backend validates ranges and audits changes.
import React, { useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useSettings } from "@/context/SettingsContext";
import { useI18n, LANGS } from "@/i18n";

const input = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

// Field types per section. "text" | "number" | "bool" | "color" | "time" | "select:<opts>"
const SECTIONS = [
  ["sec_general", [["restaurant_name", "text"], ["logo", "text"], ["primary_color", "color"], ["phone", "text"], ["address", "text"],
    ["opening_hours", "text"], ["receipt_footer", "text"], ["wifi_name", "text"], ["wifi_password", "text"]]],
  ["sec_time", [["timezone", "text"], ["business_day_start", "time"], ["business_day_end", "time"], ["language", "lang"], ["enabled_languages", "langs"]]],
  ["sec_money", [["currency", "text"], ["tax_enabled", "bool"], ["tax_rate", "number"], ["service_enabled", "bool"], ["service_charge", "number"],
    ["prices_include_tax", "bool"], ["payment_methods", "payments"], ["rounding", "rounding"]]],
  ["sec_orders", [["table_count", "number"], ["edit_window_seconds", "number"], ["require_customer_name", "bool"], ["require_table_number", "bool"],
    ["accepting_orders", "bool"], ["new_order_sound", "bool"]]],
  ["sec_inventory", [["default_low_stock_threshold", "number"], ["auto_hide_out_of_stock", "bool"], ["alert_in_app", "bool"]]],
  ["sec_security", [["session_hours", "number"], ["min_password_length", "number"]]],
];

// Toggle switch used for all boolean settings.
export const Toggle = ({ id, checked, onChange }) => (
  <button data-testid={`toggle-${id}`} type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}
    className={`relative w-12 h-7 rounded-full transition-colors duration-200 ${checked ? "brand-bg" : "bg-neutral-300"}`}>
    <span className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-transform duration-200 ${checked ? "start-6" : "start-1"}`} />
  </button>
);

export function SettingsTab({ Panel }) {
  const { t } = useI18n();
  const { settings, setSettings } = useSettings();
  const [f, setF] = useState({ ...settings });
  const [open, setOpen] = useState("sec_general");
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const save = async () => {
    try {
      const body = { ...f };
      ["tax_rate", "service_charge", "table_count", "edit_window_seconds", "default_low_stock_threshold", "session_hours", "min_password_length"]
        .forEach((k) => { body[k] = Number(body[k]); });
      const { data } = await api.put("/settings", body);
      setSettings(data); setF({ ...data });
      toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  // Plain function (not a component) so inputs keep focus while typing.
  const renderField = (k, type) => {
    const label = t(`s_${k}`);
    const row = (control) => (
      <div data-testid={`setting-${k}`} className="flex items-center justify-between gap-4 py-3 border-b border-neutral-100 last:border-0">
        <label className="text-sm font-medium text-neutral-700 shrink-0">{label}</label>
        <div className="w-full max-w-xs flex justify-end">{control}</div>
      </div>
    );
    if (type === "bool") return row(<Toggle id={k} checked={!!f[k]} onChange={(v) => set(k, v)} />);
    if (type === "color") return row(<input data-testid={`input-${k}`} type="color" className="h-11 w-20 rounded-xl border border-neutral-200" value={f[k] || "#C94A29"} onChange={(e) => set(k, e.target.value)} />);
    if (type === "lang") return row(
      <select data-testid={`input-${k}`} className={input} value={f[k]} onChange={(e) => set(k, e.target.value)}>
        {LANGS.filter((l) => (f.enabled_languages || []).includes(l.code)).map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
      </select>);
    if (type === "langs") return row(
      <div className="flex gap-2">{LANGS.map((l) => {
        const on = (f.enabled_languages || []).includes(l.code);
        return <button key={l.code} data-testid={`lang-toggle-${l.code}`} type="button" onClick={() => {
          const next = on ? f.enabled_languages.filter((x) => x !== l.code) : [...f.enabled_languages, l.code];
          if (next.length) set("enabled_languages", next);
        }} className={`px-3 h-9 rounded-full text-xs font-bold ${on ? "brand-bg text-white" : "bg-neutral-100 text-neutral-500"}`}>{l.label}</button>;
      })}</div>);
    if (type === "payments") return row(
      <div className="flex flex-wrap gap-2 justify-end">{["cash", "card", "qris", "other"].map((m) => {
        const on = !!f.payment_methods?.[m];
        return <button key={m} data-testid={`pm-toggle-${m}`} type="button" onClick={() => set("payment_methods", { ...f.payment_methods, [m]: !on })}
          className={`px-3 h-9 rounded-full text-xs font-bold ${on ? "brand-bg text-white" : "bg-neutral-100 text-neutral-500"}`}>{t(`pm_${m}`)}</button>;
      })}</div>);
    if (type === "rounding") return row(
      <select data-testid={`input-${k}`} className={input} value={f[k]} onChange={(e) => set(k, e.target.value)}>
        {["none", "100", "500"].map((r) => <option key={r} value={r}>{t(`round_${r}`)}</option>)}
      </select>);
    return row(<input data-testid={`input-${k}`} type={type} className={input} value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)} />);
  };

  return (
    <Panel title={t("settings")} action={
      <button data-testid="save-settings-btn" onClick={save} className="min-h-[44px] px-5 rounded-xl brand-bg text-white text-sm font-medium">{t("save")}</button>
    }>
      <div className="space-y-3">
        {SECTIONS.map(([sec, fields]) => (
          <div key={sec} className="bg-white rounded-2xl border border-neutral-200">
            <button data-testid={`section-${sec}`} onClick={() => setOpen(open === sec ? "" : sec)}
              className="w-full flex items-center justify-between p-5 text-start font-display font-bold text-lg">
              {t(sec)} <span className="text-neutral-400 text-sm">{open === sec ? "−" : "+"}</span>
            </button>
            {open === sec && <div className="px-5 pb-3">{fields.map(([k, type]) => <React.Fragment key={k}>{renderField(k, type)}</React.Fragment>)}</div>}
          </div>
        ))}
      </div>
    </Panel>
  );
}
