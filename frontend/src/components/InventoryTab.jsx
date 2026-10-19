import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { History, Plus, Package, RotateCcw, Trash2, Pencil } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useWs, staffWsQuery } from "@/lib/ws";
import { useI18n } from "@/i18n";

const input = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

export function InventoryTab({ Panel }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [form, setForm] = useState(null);
  const [movement, setMovement] = useState(null);
  const [history, setHistory] = useState(null);

  const load = async () => {
    const [stock, low] = await Promise.all([api.get("/inventory"), api.get("/inventory/alerts/active")]);
    setItems(stock.data); setAlerts(low.data);
  };
  useEffect(() => { load().catch((e) => toast.error(errMsg(e))); }, []);
  useWs((event) => {
    if (event === "inventory_updated" || event === "inventory_alert") load().catch(() => {});
  }, staffWsQuery());

  const save = async () => {
    try {
      const body = { name: form.name, name_en: form.name_en, name_ar: form.name_ar, unit: form.unit,
        low_stock_threshold: form.low_stock_threshold === "" ? null : Number(form.low_stock_threshold),
        cost_per_unit: form.cost_per_unit === "" ? null : Number(form.cost_per_unit) };
      if (form.id) await api.put(`/inventory/${form.id}`, body);
      else await api.post("/inventory", { ...body, initial_quantity: Number(form.initial_quantity) });
      setForm(null); await load(); toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const submitMovement = async () => {
    try {
      await api.post(`/inventory/${movement.item.id}/movements`, {
        kind: movement.kind, quantity: Number(movement.quantity), reason: movement.reason,
      });
      setMovement(null); await load(); toast.success(t("stockSaved"));
    } catch (e) { toast.error(errMsg(e)); }
  };

  const openHistory = async (item) => {
    try {
      const { data } = await api.get(`/inventory/${item.id}/movements`);
      setHistory({ item, movements: data });
    } catch (e) { toast.error(errMsg(e)); }
  };

  const toggleActive = async (item) => {
    try { await api.put(`/inventory/${item.id}`, { active: !item.active }); await load(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Panel title={t("inventory")} action={
      <button onClick={() => setForm({ name: "", name_en: "", name_ar: "", unit: "", initial_quantity: "0", low_stock_threshold: "", cost_per_unit: "" })}
        className="min-h-[44px] px-4 rounded-xl brand-bg text-white text-sm font-medium flex items-center gap-2"><Plus className="w-4 h-4" />{t("addStockItem")}</button>
    }>
      {alerts.length > 0 && <div className="mb-5 p-4 rounded-xl bg-amber-50 border border-amber-200 text-sm text-amber-900">{t("lowStockAlert")}: {alerts.map((x) => x.name).join("، ")}</div>}
      {items.length === 0 ? <div className="rounded-2xl border border-dashed border-neutral-300 p-10 text-center text-neutral-500"><Package className="mx-auto mb-2" />{t("noStockItems")}</div> :
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {items.map((item) => {
            const threshold = Number(item.effective_low_stock_threshold || 0);
            const qty = Number(item.quantity || 0);
            const low = item.active && qty <= threshold;
            const pct = threshold > 0 ? Math.min(100, Math.max(5, qty / (threshold * 2) * 100)) : (qty > 0 ? 100 : 0);
            return <div key={item.id} className={`bg-white rounded-2xl border p-5 ${low ? "border-amber-300" : "border-neutral-200"} ${!item.active ? "opacity-60" : ""}`}>
              <div className="flex justify-between gap-2"><div><h3 className="font-display font-bold">{item.name}</h3><p className="text-xs text-neutral-500">{item.name_en || item.name_ar || " "}</p></div>
                <span className={`text-xs font-semibold h-fit rounded-full px-2.5 py-1 ${!item.active ? "bg-neutral-100 text-neutral-500" : low ? "bg-amber-100 text-amber-800" : "bg-emerald-50 text-emerald-700"}`}>{!item.active ? t("inactive") : low ? t("lowStock") : t("stockOk")}</span></div>
              <div className="mt-4 flex items-end gap-2"><strong className="font-display text-3xl">{qty}</strong><span className="text-sm text-neutral-500 mb-1">{item.unit}</span></div>
              <div className="mt-2 h-2 rounded-full bg-neutral-100 overflow-hidden"><div className={`h-full rounded-full ${low ? "bg-amber-500" : "brand-bg"}`} style={{ width: `${pct}%` }} /></div>
              <p className="text-xs text-neutral-500 mt-2">{t("lowStockThreshold")}: {threshold} {item.unit}</p>
              <div className="flex gap-2 mt-4">
                <button disabled={!item.active} onClick={() => setMovement({ item, kind: "restock", quantity: "", reason: "" })} className="flex-1 min-h-10 rounded-lg brand-bg text-white text-xs font-medium disabled:opacity-50"><RotateCcw className="inline w-3.5 h-3.5 me-1" />{t("restock")}</button>
                <button disabled={!item.active} onClick={() => setMovement({ item, kind: "waste", quantity: "", reason: "" })} className="flex-1 min-h-10 rounded-lg border border-neutral-200 text-xs font-medium disabled:opacity-50"><Trash2 className="inline w-3.5 h-3.5 me-1" />{t("recordWaste")}</button>
                <button onClick={() => openHistory(item)} title={t("movementHistory")} className="w-10 h-10 rounded-lg border border-neutral-200 grid place-items-center"><History className="w-4 h-4" /></button>
              </div>
              <button disabled={!item.active} onClick={() => setMovement({ item, kind: "adjustment", quantity: "", reason: "" })} className="w-full mt-2 min-h-9 rounded-lg border border-neutral-200 text-xs font-medium disabled:opacity-50">{t("adjustStock")}</button>
              <div className="flex justify-between items-center mt-2"><button onClick={() => setForm({ id: item.id, name: item.name, name_en: item.name_en || "", name_ar: item.name_ar || "", unit: item.unit, initial_quantity: "0", low_stock_threshold: item.low_stock_threshold ?? "", cost_per_unit: item.cost_per_unit ?? "" })} className="text-xs text-neutral-500 flex items-center gap-1"><Pencil className="w-3 h-3" />{t("edit")}</button><button onClick={() => toggleActive(item)} className="text-xs text-neutral-500 underline">{item.active ? t("archiveStockItem") : t("restoreStockItem")}</button></div>
            </div>;
          })}
        </div>}

      {form && <Modal title={form.id ? t("edit") : t("addStockItem")} onClose={() => setForm(null)}>
        <div className="space-y-3">
          <input className={input} placeholder={t("name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <div className="grid grid-cols-2 gap-3"><input className={input} placeholder={`${t("name")} (EN)`} value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} />
            <input className={input} placeholder={`${t("name")} (AR)`} value={form.name_ar} onChange={(e) => setForm({ ...form, name_ar: e.target.value })} /></div>
          <div className={`grid ${form.id ? "grid-cols-1" : "grid-cols-2"} gap-3`}><input className={input} placeholder={t("unit")} value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} />
            {!form.id && <input className={input} type="number" min="0" step="any" placeholder={t("initialStock")} value={form.initial_quantity} onChange={(e) => setForm({ ...form, initial_quantity: e.target.value })} />}</div>
          <input className={input} type="number" min="0" step="any" placeholder={t("lowStockThresholdDefault")} value={form.low_stock_threshold} onChange={(e) => setForm({ ...form, low_stock_threshold: e.target.value })} />
          <input className={input} type="number" min="0" step="any" placeholder={t("costPerUnitOptional")} value={form.cost_per_unit} onChange={(e) => setForm({ ...form, cost_per_unit: e.target.value })} />
        </div>
        <div className="flex gap-3 mt-5"><button onClick={() => setForm(null)} className="flex-1 h-11 rounded-xl border">{t("cancel")}</button><button onClick={save} className="flex-1 h-11 rounded-xl brand-bg text-white">{t("save")}</button></div>
      </Modal>}

      {movement && <Modal title={`${t(movement.kind === "restock" ? "restock" : movement.kind === "waste" ? "recordWaste" : "adjustStock")}: ${movement.item.name}`} onClose={() => setMovement(null)}>
        <div className="space-y-3"><input autoFocus className={input} type="number" min={movement.kind === "adjustment" ? undefined : "0.001"} step="any" placeholder={`${t("quantity")} (${movement.item.unit})${movement.kind === "adjustment" ? ` · ${t("signedQuantity")}` : ""}`} value={movement.quantity} onChange={(e) => setMovement({ ...movement, quantity: e.target.value })} />
          <input className={input} placeholder={t("reasonRequired")} value={movement.reason} onChange={(e) => setMovement({ ...movement, reason: e.target.value })} /></div>
        <div className="flex gap-3 mt-5"><button onClick={() => setMovement(null)} className="flex-1 h-11 rounded-xl border">{t("cancel")}</button><button onClick={submitMovement} disabled={!movement.quantity || !movement.reason.trim()} className="flex-1 h-11 rounded-xl brand-bg text-white disabled:opacity-50">{t("save")}</button></div>
      </Modal>}

      {history && <Modal title={`${t("movementHistory")}: ${history.item.name}`} onClose={() => setHistory(null)} wide>
        <div className="max-h-[55vh] overflow-y-auto divide-y divide-neutral-100">
          {history.movements.length === 0 && <p className="py-5 text-sm text-neutral-500">—</p>}
          {history.movements.map((row) => <div key={row.id} className="py-3 flex justify-between gap-4 text-sm"><div><div className="font-medium">{t(`movement_${row.kind}`)} · {row.reason}</div><div className="text-xs text-neutral-500">{row.actor_name} · {new Date(row.created_at).toLocaleString()}</div></div><strong className={row.delta < 0 ? "text-red-600" : "text-emerald-700"}>{row.delta > 0 ? "+" : ""}{row.delta} {row.unit}</strong></div>)}
        </div>
      </Modal>}
    </Panel>
  );
}

function Modal({ title, children, onClose, wide = false }) {
  return <div className="fixed inset-0 z-50 bg-black/40 grid place-items-center p-4" onClick={onClose}><div className={`bg-white rounded-2xl p-6 w-full ${wide ? "max-w-2xl" : "max-w-lg"}`} onClick={(e) => e.stopPropagation()}><h3 className="font-display font-bold text-xl mb-4">{title}</h3>{children}</div></div>;
}
