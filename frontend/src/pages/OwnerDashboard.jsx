import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { LogOut, ChefHat, ShieldCheck, LayoutDashboard, UtensilsCrossed, Users, BarChart3, Settings as SettingsIcon, ScrollText, QrCode, Plus, Trash2, Package } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { api, money, errMsg, BACKEND_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSettings } from "@/context/SettingsContext";
import { useI18n } from "@/i18n";
import { LangSwitch, ChangePasswordButton } from "@/components/Shared";
import { StaffTab } from "@/components/StaffTab";
import { SettingsTab } from "@/components/SettingsTab";
import { AdminTab } from "@/components/AdminTab";
import CashierDashboard from "@/pages/CashierDashboard";
import { InventoryTab } from "@/components/InventoryTab";

const TABS = [
  ["orders", LayoutDashboard], ["menu", UtensilsCrossed], ["inventory", Package], ["staff", Users],
  ["reports", BarChart3], ["tables", QrCode], ["auditLog", ScrollText], ["settings", SettingsIcon],
];
// Only the super admin gets the extra tab.
const ADMIN_TAB = ["adminPanel", ShieldCheck];

export default function OwnerDashboard() {
  const { user, logout } = useAuth();
  const { settings } = useSettings();
  const { t } = useI18n();
  const [tab, setTab] = useState("orders");

  return (
    <div className="min-h-screen bg-[#F8F7F4] md:flex">
      <aside className="bg-[#2E3D36] text-white md:w-64 md:min-h-screen p-5">
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-xl brand-bg grid place-items-center"><ChefHat className="w-5 h-5" /></div>
          <div>
            <div className="font-display font-bold leading-tight">{settings.restaurant_name}</div>
            <div className="text-xs text-white/60">{user.name}</div>
          </div>
        </div>
        <nav className="flex md:flex-col gap-1.5 overflow-x-auto no-scrollbar">
          {[...TABS, ...(user.role === "super_admin" ? [ADMIN_TAB] : [])].map(([k, Icon]) => (
            <button
              key={k} data-testid={`owner-tab-${k}`} onClick={() => setTab(k)}
              className={`shrink-0 flex items-center gap-2.5 min-h-[44px] px-4 rounded-xl text-sm font-medium transition-colors duration-200 ${
                tab === k ? "brand-bg text-white" : "text-white/70 hover:bg-white/10"
              }`}
            >
              <Icon className="w-4 h-4" /> {t(k)}
            </button>
          ))}
        </nav>
        <div className="mt-8 flex items-center gap-3">
          <LangSwitch dark />
          <ChangePasswordButton dark />
          <button data-testid="owner-logout-btn" onClick={logout} className="w-11 h-11 rounded-xl bg-white/10 grid place-items-center"><LogOut className="w-4 h-4" /></button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        {tab === "orders" && <CashierDashboard />}
        {tab === "menu" && <MenuTab />}
        {tab === "inventory" && <InventoryTab Panel={Panel} />}
        {tab === "staff" && <StaffTab Panel={Panel} />}
        {tab === "reports" && <ReportsTab />}
        {tab === "tables" && <TablesTab />}
        {tab === "auditLog" && <AuditTab />}
        {tab === "settings" && <SettingsTab Panel={Panel} />}
        {tab === "adminPanel" && user.role === "super_admin" && <AdminTab Panel={Panel} />}
      </main>
    </div>
  );
}

const Panel = ({ title, children, action }) => (
  <div className="p-6 md:p-8 max-w-6xl">
    <div className="flex items-center justify-between mb-6">
      <h1 className="font-display text-3xl font-bold">{title}</h1>
      {action}
    </div>
    {children}
  </div>
);

const input = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

function MenuTab() {
  const { t } = useI18n();
  const { settings } = useSettings();
  const [items, setItems] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [form, setForm] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);

  const load = () => api.get("/menu/manage").then((r) => setItems(r.data));
  useEffect(() => { load(); api.get("/inventory").then((r) => setInventory(r.data.filter((x) => x.active))); }, []);

  const blank = { name: "", description: "", name_en: "", name_ar: "", description_en: "", description_ar: "", image: "", image_thumbnail: "", savedImage: "", price: 0, discount_price: null, category: "Makanan Utama", available: true, options: [], consumes: [] };

  // Upload a menu photo using a camera or gallery file input; the server compresses it.
  const uploadImage = async (file) => {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    data.append("kind", "menu");
    setUploadingImage(true);
    try {
      const { data: uploaded } = await api.post("/uploads/images", data);
      if (form.image && form.image !== form.savedImage) {
        api.delete("/uploads/images", { data: { image: form.image } }).catch(() => {});
      }
      setForm((current) => ({ ...current, image: uploaded.image, image_thumbnail: uploaded.thumbnail }));
    } catch (e) { toast.error(errMsg(e)); }
    finally { setUploadingImage(false); }
  };

  // Remove an unsaved upload when the owner clears it or closes the form without saving.
  const closeForm = () => {
    if (form?.image && form.image !== form.savedImage) {
      api.delete("/uploads/images", { data: { image: form.image } }).catch(() => {});
    }
    setForm(null);
  };

  const removeFormImage = () => {
    if (form.image && form.image !== form.savedImage) {
      api.delete("/uploads/images", { data: { image: form.image } }).catch(() => {});
    }
    setForm({ ...form, image: "", image_thumbnail: "" });
  };

  const save = async () => {
    try {
      const { savedImage, ...body } = form;
      body.price = Number(body.price);
      body.discount_price = body.discount_price ? Number(body.discount_price) : null;
      if (form.id) await api.put(`/menu/${form.id}`, body);
      else await api.post("/menu", body);
      setForm(null); load(); toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const del = async (it) => {
    try { await api.delete(`/menu/${it.id}`); load(); toast.success(t("delete") + " ✓"); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Panel title={t("menu")} action={
      <button data-testid="add-menu-item-btn" onClick={() => setForm(blank)} className="min-h-[44px] px-4 rounded-xl brand-bg text-white text-sm font-medium flex items-center gap-2">
        <Plus className="w-4 h-4" /> {t("addItem")}
      </button>
    }>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((it) => (
          <div key={it.id} data-testid={`owner-menu-item-${it.id}`} className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
            {it.image && <img src={it.image_thumbnail || it.image} alt={it.name} className="w-full h-32 object-cover" />}
            <div className="p-4">
              <div className="font-display font-bold">{it.name}</div>
              <div className="text-xs text-neutral-500">{it.category}</div>
              <div className="mt-1 font-bold brand-text text-sm">{money(it.discount_price ?? it.price, settings.currency)}</div>
              <div className={`mt-1 text-xs ${it.available ? "text-emerald-700" : "text-red-600"}`}>
                {it.available ? t("available") : t("soldOut")}
              </div>
              <div className="mt-3 flex gap-2">
                <button data-testid={`edit-menu-${it.id}`} onClick={() => setForm({ ...it, savedImage: it.image || "" })} className="flex-1 min-h-[40px] rounded-lg border border-neutral-200 text-sm font-medium">{t("edit")}</button>
                <button data-testid={`delete-menu-${it.id}`} onClick={() => del(it)} className="w-10 h-10 rounded-lg grid place-items-center text-red-500 border border-neutral-200"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {form && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" onClick={closeForm}>
          <div data-testid="menu-form-modal" className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display font-bold text-xl mb-4">{form.id ? t("edit") : t("addItem")}</h3>
            <div className="space-y-3">
              <input data-testid="menu-name-input" className={input} placeholder={t("name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input data-testid="menu-desc-input" className={input} placeholder={t("desc")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <div className="grid grid-cols-2 gap-3">
                <input data-testid="menu-name-en-input" className={input} placeholder={`${t("name")} (EN)`} value={form.name_en || ""} onChange={(e) => setForm({ ...form, name_en: e.target.value })} />
                <input data-testid="menu-name-ar-input" dir="rtl" className={input} placeholder={`${t("name")} (AR)`} value={form.name_ar || ""} onChange={(e) => setForm({ ...form, name_ar: e.target.value })} />
                <input data-testid="menu-desc-en-input" className={input} placeholder={`${t("desc")} (EN)`} value={form.description_en || ""} onChange={(e) => setForm({ ...form, description_en: e.target.value })} />
                <input data-testid="menu-desc-ar-input" dir="rtl" className={input} placeholder={`${t("desc")} (AR)`} value={form.description_ar || ""} onChange={(e) => setForm({ ...form, description_ar: e.target.value })} />
              </div>
              <div data-testid="menu-image-input" className="rounded-xl border border-neutral-200 p-3 space-y-3">
                {form.image && <img src={form.image_thumbnail || form.image} alt={form.name || t("name")} className="w-full h-36 rounded-lg object-cover" />}
                <div className="flex flex-wrap gap-2">
                  <label className="min-h-10 px-3 rounded-lg border border-neutral-200 text-xs font-medium grid place-items-center cursor-pointer">
                    {t("imageCamera")}<input type="file" accept="image/*" capture="environment" className="hidden"
                      onChange={(e) => { uploadImage(e.target.files?.[0]); e.target.value = ""; }} />
                  </label>
                  <label className="min-h-10 px-3 rounded-lg border border-neutral-200 text-xs font-medium grid place-items-center cursor-pointer">
                    {t("imageGallery")}<input type="file" accept="image/*" className="hidden"
                      onChange={(e) => { uploadImage(e.target.files?.[0]); e.target.value = ""; }} />
                  </label>
                  {form.image && <button type="button" onClick={removeFormImage}
                    className="min-h-10 px-3 rounded-lg border border-neutral-200 text-xs text-red-600">{t("removeImage")}</button>}
                </div>
                {uploadingImage && <span className="text-xs text-neutral-500">{t("uploadingImage")}</span>}
              </div>
              <input data-testid="menu-category-input" className={input} placeholder={t("category")} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
              <div className="flex gap-3">
                <input data-testid="menu-price-input" type="number" className={input} placeholder={t("price")} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
                <input data-testid="menu-discount-input" type="number" className={input} placeholder="Discount" value={form.discount_price ?? ""} onChange={(e) => setForm({ ...form, discount_price: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input data-testid="menu-available-toggle" type="checkbox" checked={form.available} onChange={(e) => setForm({ ...form, available: e.target.checked })} />
                {t("available")}
              </label>
              <OptionEditor form={form} setForm={setForm} />
              <RecipeEditor form={form} setForm={setForm} inventory={inventory} />
            </div>
            <div className="mt-5 flex gap-3">
              <button data-testid="cancel-menu-btn" onClick={closeForm} className="flex-1 h-12 rounded-xl border border-neutral-200 font-medium">{t("cancel")}</button>
              <button data-testid="save-menu-btn" onClick={save} disabled={uploadingImage} className="flex-1 h-12 rounded-xl brand-bg text-white font-medium disabled:opacity-50">{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function RecipeEditor({ form, setForm, inventory }) {
  const { t } = useI18n();
  const rows = form.consumes || [];
  const update = (next) => setForm({ ...form, consumes: next });
  return (
    <div className="border-t border-neutral-100 pt-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold">{t("recipe")}</span>
        <button type="button" onClick={() => update([...rows, { inventory_item_id: "", qty_per_unit: 1 }])} className="text-xs brand-text font-medium">+ {t("addIngredient")}</button>
      </div>
      {rows.map((row, i) => (
        <div key={i} className="flex gap-2 items-center">
          <select className="flex-1 h-10 rounded-lg border border-neutral-200 px-2 text-sm" value={row.inventory_item_id}
            onChange={(e) => update(rows.map((x, j) => j === i ? { ...x, inventory_item_id: e.target.value } : x))}>
            <option value="">{t("chooseIngredient")}</option>
            {inventory.map((x) => <option key={x.id} value={x.id}>{x.name} ({x.unit})</option>)}
          </select>
          <input type="number" min="0.001" step="any" className="w-24 h-10 rounded-lg border border-neutral-200 px-2 text-sm" value={row.qty_per_unit}
            onChange={(e) => update(rows.map((x, j) => j === i ? { ...x, qty_per_unit: Number(e.target.value) } : x))} />
          <button type="button" onClick={() => update(rows.filter((_, j) => j !== i))} className="text-red-500"><Trash2 className="w-4 h-4" /></button>
        </div>
      ))}
      {inventory.length === 0 && <p className="text-xs text-neutral-500">{t("addInventoryFirst")}</p>}
    </div>
  );
}

function OptionEditor({ form, setForm }) {
  const { t } = useI18n();
  const groups = form.options || [];
  const upd = (gs) => setForm({ ...form, options: gs });
  return (
    <div className="border-t border-neutral-100 pt-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold">{t("options")}</span>
        <button data-testid="add-option-group-btn" onClick={() => upd([...groups, { name: "", required: false, choices: [] }])} className="text-xs brand-text font-medium">+ Grup</button>
      </div>
      {groups.map((g, gi) => (
        <div key={gi} className="bg-[#F8F7F4] rounded-xl p-3 mb-2 space-y-2">
          <div className="flex gap-2 items-center">
            <input data-testid={`option-group-name-${gi}`} className="flex-1 h-9 px-3 rounded-lg border border-neutral-200 text-sm" placeholder="Nama grup" value={g.name}
              onChange={(e) => upd(groups.map((x, i) => (i === gi ? { ...x, name: e.target.value } : x)))} />
            <label className="text-xs flex items-center gap-1">
              <input type="checkbox" checked={g.required} onChange={(e) => upd(groups.map((x, i) => (i === gi ? { ...x, required: e.target.checked } : x)))} /> wajib
            </label>
            <button data-testid={`remove-group-${gi}`} onClick={() => upd(groups.filter((_, i) => i !== gi))} className="text-red-500"><Trash2 className="w-4 h-4" /></button>
          </div>
          {g.choices.map((c, ci) => (
            <div key={ci} className="flex gap-2">
              <input className="flex-1 h-9 px-3 rounded-lg border border-neutral-200 text-sm" placeholder="Label" value={c.label}
                onChange={(e) => upd(groups.map((x, i) => (i === gi ? { ...x, choices: x.choices.map((y, j) => (j === ci ? { ...y, label: e.target.value } : y)) } : x)))} />
              <input type="number" className="w-28 h-9 px-3 rounded-lg border border-neutral-200 text-sm" placeholder="+Harga" value={c.price_delta}
                onChange={(e) => upd(groups.map((x, i) => (i === gi ? { ...x, choices: x.choices.map((y, j) => (j === ci ? { ...y, price_delta: Number(e.target.value) } : y)) } : x)))} />
            </div>
          ))}
          <button data-testid={`add-choice-${gi}`} onClick={() => upd(groups.map((x, i) => (i === gi ? { ...x, choices: [...x.choices, { label: "", price_delta: 0 }] } : x)))} className="text-xs brand-text font-medium">+ Pilihan</button>
        </div>
      ))}
    </div>
  );
}

function ReportsTab() {
  const { t } = useI18n();
  const { settings } = useSettings();
  const [period, setPeriod] = useState("day");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [data, setData] = useState(null);
  const [billing, setBilling] = useState(null);
  useEffect(() => { api.get("/billing/summary").then((r) => setBilling(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    if (period === "custom" && (!startDate || !endDate)) return;
    setData(null);
    api.get("/reports", { params: period === "custom" ? { start_date: startDate, end_date: endDate } : { period } }).then((r) => setData(r.data));
  }, [period, startDate, endDate]);
  const exportCsv = () => {
    const rows = [["section", "name", "count", "amount"], ["summary", "orders", data.orders_count, ""],
      ["summary", "paid", data.paid_count, ""], ["summary", "restaurant_revenue", "", data.revenue],
      ["summary", "system_fees", "", data.system_fees], ...data.payment_methods.map((x) => ["payment", x.method, x.orders, x.revenue]),
      ...data.cashier_performance.map((x) => ["cashier", x.cashier_name, x.orders, x.revenue]),
      ...data.best_sellers.map((x) => ["best_seller", x.name, x.qty, ""]), ...data.worst_sellers.map((x) => ["worst_seller", x.name, x.qty, ""])];
    const csv = rows.map((r) => r.map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" }));
    a.download = `growth-board-${data.start_date}-${data.end_date}.csv`; a.click(); URL.revokeObjectURL(a.href);
  };
  if (!data) return <Panel title={t("reports")}>...</Panel>;

  return (
    <Panel title={t("reports")} action={
      <div className="flex gap-2">
        {["day", "week", "month"].map((p) => (
          <button key={p} data-testid={`period-${p}`} onClick={() => setPeriod(p)}
            className={`min-h-[40px] px-4 rounded-xl text-sm font-medium ${period === p ? "brand-bg text-white" : "bg-white border border-neutral-200"}`}>
            {p}
          </button>
        ))}
        <button data-testid="period-custom" onClick={() => setPeriod("custom")} className={`min-h-[40px] px-4 rounded-xl text-sm font-medium ${period === "custom" ? "brand-bg text-white" : "bg-white border border-neutral-200"}`}>{t("dateRange")}</button>
        <button data-testid="report-export-csv" onClick={exportCsv} className="min-h-[40px] px-4 rounded-xl bg-white border border-neutral-200 text-sm">{t("exportCsv")}</button>
        <button data-testid="report-print-pdf" onClick={() => window.print()} className="min-h-[40px] px-4 rounded-xl bg-white border border-neutral-200 text-sm">{t("printPdf")}</button>
      </div>
    }>
      {period === "custom" && <div className="flex flex-wrap gap-3 mb-5">
        <label className="text-sm">{t("startDate")} <input data-testid="report-start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="ms-2 h-10 px-3 border rounded-xl" /></label>
        <label className="text-sm">{t("endDate")} <input data-testid="report-end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="ms-2 h-10 px-3 border rounded-xl" /></label>
      </div>}
      {billing && <div data-testid="owner-billing-summary" className="bg-white rounded-2xl border border-neutral-200 p-5 mb-6"><h3 className="font-display font-bold mb-2">{t("billingSummary")}</h3>
        <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm"><span>{t("month")}: <b>{billing.month}</b></span><span>{t("systemFee")}: <b>{money(billing.fee_per_invoice, billing.currency)}</b></span><span>{t("invoiceCount")}: <b>{billing.invoice_count}</b></span>
          {billing.mode === "monthly" ? <span>{t("amountDue")}: <b>{money(billing.amount_due, billing.currency)}</b> · {billing.monthly_paid ? t("paidStamp") : t("unpaid")}</span> : <span>{t("balance")}: <b>{money(billing.balance, billing.currency)}</b></span>}
        </div>
        {billing.warning && <div className="text-amber-700 text-sm mt-3">{t("lowBalanceWarning")}</div>}
      </div>}
      <div data-testid="report-metrics" className="grid sm:grid-cols-4 gap-4 mb-8">
        {[[t("orders"), data.orders_count], [t("revenue"), money(data.revenue, settings.currency)],
          [t("avgOrder"), money(data.avg_order_value, settings.currency)], [t("systemFee"), money(data.system_fees, settings.currency)], [t("systemFeeTax"), money(data.system_fee_tax, settings.currency)],
          [t("paidCount"), data.paid_count], [t("unpaidCount"), data.unpaid_count], [t("cancelledCount"), data.cancelled_count]].map(([l, v]) => (
          <div key={l} className="bg-white rounded-2xl border border-neutral-200 p-5">
            <div className="text-xs text-neutral-500">{l}</div>
            <div className="font-display text-2xl font-bold mt-1">{v}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-neutral-200 p-5">
          <h3 className="font-display font-bold mb-3">{t("busiestHours")}</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.busiest_hours}>
              <XAxis dataKey="hour" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="orders" fill="#C94A29" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="grid gap-6">
          {[[t("bestSellers"), data.best_sellers], [t("worstSellers"), data.worst_sellers]].map(([title, list]) => (
            <div key={title} className="bg-white rounded-2xl border border-neutral-200 p-5">
              <h3 className="font-display font-bold mb-2">{title}</h3>
              {list.length === 0 && <p className="text-sm text-neutral-500">—</p>}
              {list.map((x) => (
                <div key={x.name} className="flex justify-between text-sm py-1">
                  <span>{x.name}</span><b>{x.qty}</b>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="grid lg:grid-cols-3 gap-6 mt-6">
        <div className="bg-white rounded-2xl border border-neutral-200 p-5"><h3 className="font-display font-bold mb-3">{t("paymentBreakdown")}</h3>{data.payment_methods.map((x) => <div key={x.method} className="flex justify-between text-sm py-1"><span>{t(`pm_${x.method}`)}</span><span>{x.orders} · {money(x.revenue, settings.currency)}</span></div>)}</div>
        <div className="bg-white rounded-2xl border border-neutral-200 p-5"><h3 className="font-display font-bold mb-3">{t("cashierPerformance")}</h3>{data.cashier_performance.map((x) => <div key={x.cashier_id} className="flex justify-between text-sm py-1"><span>{x.cashier_name}</span><span>{x.orders} · {money(x.revenue, settings.currency)}</span></div>)}</div>
        <div className="bg-white rounded-2xl border border-neutral-200 p-5"><h3 className="font-display font-bold mb-3">{t("ratingsSummary")}</h3><div className="text-sm space-y-1"><div>{t("ordersCount")}: {data.ratings.count}</div><div>{t("food")}: {data.ratings.food}/5</div><div>{t("service")}: {data.ratings.service}/5</div><div>{t("speed")}: {data.ratings.speed}/5</div></div></div>
      </div>
    </Panel>
  );
}

function TablesTab() {
  const { t } = useI18n();
  const { settings } = useSettings();
  const origin = window.location.origin;
  const tables = Array.from({ length: settings.table_count || 5 }, (_, i) => i + 1);
  return (
    <Panel title={t("tables")}>
      <div className="grid sm:grid-cols-3 lg:grid-cols-4 gap-5">
        {tables.map((n) => {
          const url = `${origin}/t/${n}`;
          return (
            <div key={n} data-testid={`qr-table-${n}`} className="bg-white rounded-2xl border border-neutral-200 p-5 text-center">
              <img alt={`QR ${n}`} className="w-full aspect-square object-contain"
                src={`https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=8&data=${encodeURIComponent(url)}`} />
              <div className="font-display font-bold mt-3">{t("table")} {n}</div>
              <a href={url} className="text-xs brand-text break-all">{url}</a>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function AuditTab() {
  const { t } = useI18n();
  const [logs, setLogs] = useState([]);
  useEffect(() => { api.get("/audit").then((r) => setLogs(r.data)); }, []);
  return (
    <Panel title={t("auditLog")}>
      <div data-testid="audit-list" className="bg-white rounded-2xl border border-neutral-200 divide-y divide-neutral-100">
        {logs.map((l) => (
          <div key={l.id} className="p-4 flex justify-between gap-4 text-sm">
            <div>
              <div className="font-medium">{l.action}</div>
              <div className="text-neutral-500 text-xs">{l.detail}</div>
            </div>
            <div className="text-xs text-neutral-400 whitespace-nowrap">
              {l.user_name} · {new Date(l.created_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

