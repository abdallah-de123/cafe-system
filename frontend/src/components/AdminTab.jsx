// Super-admin-only panel: license, feature flags, billing configuration (stored now, enforced in Phase 4).
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { ShieldCheck } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useI18n } from "@/i18n";
import { Toggle } from "@/components/SettingsTab";

const input = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

export function AdminTab({ Panel }) {
  const { t } = useI18n();
  const [f, setF] = useState(null);

  useEffect(() => { api.get("/admin/settings").then((r) => setF(r.data)).catch((e) => toast.error(errMsg(e))); }, []);

  const save = async () => {
    try {
      const body = { ...f, fee_per_invoice: Number(f.fee_per_invoice), low_balance_warning: Number(f.low_balance_warning), grace_invoices: Number(f.grace_invoices) };
      if (!body.license_expires_at) delete body.license_expires_at;
      const { data } = await api.put("/admin/settings", body);
      setF(data); toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  if (!f) return null;
  const row = (k, control) => (
    <div data-testid={`admin-setting-${k}`} className="flex items-center justify-between gap-4 py-3 border-b border-neutral-100 last:border-0">
      <label className="text-sm font-medium text-neutral-700 shrink-0">{t(`a_${k}`)}</label>
      <div className="w-full max-w-xs flex justify-end">{control}</div>
    </div>
  );
  const text = (k, type = "text") => <input data-testid={`admin-input-${k}`} type={type} className={input} value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} />;
  const sel = (k, opts, prefix) => (
    <select data-testid={`admin-input-${k}`} className={input} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })}>
      {opts.map((o) => <option key={o} value={o}>{t(`${prefix}_${o}`)}</option>)}
    </select>
  );

  return (
    <Panel title={t("adminPanel")} action={
      <button data-testid="save-admin-settings-btn" onClick={save} className="min-h-[44px] px-5 rounded-xl brand-bg text-white text-sm font-medium">{t("save")}</button>
    }>
      <div className="mb-4 rounded-2xl bg-[#2E3D36] text-white/80 text-sm p-4 flex items-center gap-3">
        <ShieldCheck className="w-5 h-5 shrink-0" /> {t("adminNote")}
      </div>
      <div className="bg-white rounded-2xl border border-neutral-200 px-5 py-2">
        {row("license_expires_at", text("license_expires_at"))}
        {row("seed_demo", <Toggle id="seed_demo" checked={!!f.feature_flags?.seed_demo} onChange={(v) => setF({ ...f, feature_flags: { ...f.feature_flags, seed_demo: v } })} />)}
        {row("billing_enabled", <Toggle id="billing_enabled" checked={!!f.billing_enabled} onChange={(v) => setF({ ...f, billing_enabled: v })} />)}
        {row("billing_mode", sel("billing_mode", ["monthly", "prepaid"], "mode"))}
        {row("fee_per_invoice", text("fee_per_invoice", "number"))}
        {row("low_balance_warning", text("low_balance_warning", "number"))}
        {row("zero_balance_behavior", sel("zero_balance_behavior", ["warn", "warn_grace", "block"], "zb"))}
        {row("grace_invoices", text("grace_invoices", "number"))}
        {row("reversal_refunds_fee", <Toggle id="reversal_refunds_fee" checked={!!f.reversal_refunds_fee} onChange={(v) => setF({ ...f, reversal_refunds_fee: v })} />)}
      </div>
    </Panel>
  );
}
