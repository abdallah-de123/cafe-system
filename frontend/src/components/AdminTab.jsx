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
  const [usage, setUsage] = useState(null);
  const [topUpAmount, setTopUpAmount] = useState("");
  const [topUpNote, setTopUpNote] = useState("");

  const loadUsage = () => api.get("/admin/billing/usage").then((r) => setUsage(r.data)).catch(() => {});
  useEffect(() => { api.get("/admin/settings").then((r) => setF(r.data)).catch((e) => toast.error(errMsg(e))); loadUsage(); }, []);

  const save = async () => {
    try {
      const body = { ...f, fee_per_invoice: Number(f.fee_per_invoice), low_balance_warning: Number(f.low_balance_warning), grace_invoices: Number(f.grace_invoices) };
      if (!body.license_expires_at) delete body.license_expires_at;
      const { data } = await api.put("/admin/settings", body);
      setF(data); toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const topUp = async () => {
    try {
      await api.post("/admin/billing/topups", { amount: Number(topUpAmount), note: topUpNote });
      setTopUpAmount(""); setTopUpNote(""); loadUsage(); toast.success(t("save"));
    } catch (e) { toast.error(errMsg(e)); }
  };

  const markMonthPaid = async () => {
    try {
      await api.post("/admin/billing/month-paid", { month: usage.month, note: "", paid: !usage.monthly_paid });
      loadUsage(); toast.success(t("save"));
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
      {usage && <div data-testid="admin-billing-usage" className="bg-white rounded-2xl border border-neutral-200 p-5 mt-5 space-y-4">
        <h3 className="font-display font-bold">{t("billingSummary")} · {usage.month}</h3>
        <div className="flex flex-wrap gap-6 text-sm"><span>{t("invoiceCount")}: <b>{usage.invoice_count}</b></span><span>{t("systemFee")}: <b>{usage.fees} {usage.currency}</b></span><span>{t("balance")}: <b>{usage.balance} {usage.currency}</b></span></div>
        <div className="space-y-1">{usage.days.map((d) => <div key={d.date} className="flex justify-between text-sm border-b py-2"><span>{d.date} · {d.count}</span><b>{d.fees} {usage.currency}</b></div>)}</div>
        {f.billing_mode === "monthly" && <div className="flex items-center gap-3"><span className="text-sm">{usage.monthly_paid ? t("paidStamp") : t("unpaid")}</span><button onClick={markMonthPaid} className="min-h-10 px-4 rounded-xl brand-bg text-white text-sm">{t(usage.monthly_paid ? "markUnpaid" : "markPaid")}</button></div>}
        {f.billing_mode === "prepaid" && <div className="grid sm:grid-cols-[1fr_2fr_auto] gap-2"><input aria-label={t("topUpAmount")} type="number" min="0.01" value={topUpAmount} onChange={(e) => setTopUpAmount(e.target.value)} placeholder={t("topUpAmount")} className={input} /><input aria-label={t("note")} value={topUpNote} onChange={(e) => setTopUpNote(e.target.value)} placeholder={t("note")} className={input} /><button disabled={!Number(topUpAmount)} onClick={topUp} className="min-h-11 px-4 rounded-xl brand-bg text-white disabled:opacity-50">{t("topUp")}</button></div>}
      </div>}
    </Panel>
  );
}
