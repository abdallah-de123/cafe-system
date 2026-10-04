import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { LogOut, ChefHat, LayoutDashboard, UtensilsCrossed, Users, BarChart3, Settings as SettingsIcon, ScrollText, QrCode, Plus, Trash2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { api, money, errMsg, BACKEND_URL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useSettings } from "@/context/SettingsContext";
import { useI18n } from "@/i18n";
import { LangSwitch } from "@/components/Shared";
import CashierDashboard from "@/pages/CashierDashboard";

const TABS = [
  ["orders", LayoutDashboard], ["menu", UtensilsCrossed], ["staff", Users],
  ["reports", BarChart3], ["tables", QrCode], ["auditLog", ScrollText], ["settings", SettingsIcon],
];

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
          {TABS.map(([k, Icon]) => (
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
          <button data-testid="owner-logout-btn" onClick={logout} className="w-11 h-11 rounded-xl bg-white/10 grid place-items-center"><LogOut className="w-4 h-4" /></button>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        {tab === "orders" && <CashierDashboard />}
        {tab === "menu" && <MenuTab />}
        {tab === "staff" && <StaffTab />}
        {tab === "reports" && <ReportsTab />}
        {tab === "tables" && <TablesTab />}
        {tab === "auditLog" && <AuditTab />}
        {tab === "settings" && <SettingsTab />}
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
  const [form, setForm] = useState(null);

  const load = () => api.get("/menu").then((r) => setItems(r.data));
  useEffect(() => { load(); }, []);

  const blank = { name: "", description: "", image: "", price: 0, discount_price: null, category: "Makanan Utama", available: true, options: [] };

  const save = async () => {
    try {
      const body = { ...form, price: Number(form.price), discount_price: form.discount_price ? Number(form.discount_price) : null };
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
            <img src={it.image} alt={it.name} className="w-full h-32 object-cover" />
            <div className="p-4">
              <div className="font-display font-bold">{it.name}</div>
              <div className="text-xs text-neutral-500">{it.category}</div>
              <div className="mt-1 font-bold brand-text text-sm">{money(it.discount_price ?? it.price, settings.currency)}</div>
              <div className={`mt-1 text-xs ${it.available ? "text-emerald-700" : "text-red-600"}`}>
                {it.available ? t("available") : "Habis"}
              </div>
              <div className="mt-3 flex gap-2">
                <button data-testid={`edit-menu-${it.id}`} onClick={() => setForm({ ...it })} className="flex-1 min-h-[40px] rounded-lg border border-neutral-200 text-sm font-medium">{t("edit")}</button>
                <button data-testid={`delete-menu-${it.id}`} onClick={() => del(it)} className="w-10 h-10 rounded-lg grid place-items-center text-red-500 border border-neutral-200"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {form && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" onClick={() => setForm(null)}>
          <div data-testid="menu-form-modal" className="bg-white rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display font-bold text-xl mb-4">{form.id ? t("edit") : t("addItem")}</h3>
            <div className="space-y-3">
              <input data-testid="menu-name-input" className={input} placeholder={t("name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input data-testid="menu-desc-input" className={input} placeholder={t("desc")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <input data-testid="menu-image-input" className={input} placeholder="Image URL" value={form.image} onChange={(e) => setForm({ ...form, image: e.target.value })} />
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
            </div>
            <div className="mt-5 flex gap-3">
              <button data-testid="cancel-menu-btn" onClick={() => setForm(null)} className="flex-1 h-12 rounded-xl border border-neutral-200 font-medium">{t("cancel")}</button>
              <button data-testid="save-menu-btn" onClick={save} className="flex-1 h-12 rounded-xl brand-bg text-white font-medium">{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </Panel>
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

function StaffTab() {
  const { t } = useI18n();
  const [staff, setStaff] = useState([]);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "cashier" });
  const load = () => api.get("/staff").then((r) => setStaff(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    try { await api.post("/staff", form); setForm({ name: "", email: "", password: "", role: "cashier" }); load(); toast.success(t("addStaff") + " ✓"); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const toggle = async (s) => {
    try { await api.put(`/staff/${s.id}`, { active: !(s.active !== false) }); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Panel title={t("staff")}>
      <div className="bg-white rounded-2xl border border-neutral-200 p-5 mb-6 grid sm:grid-cols-4 gap-3">
        <input data-testid="staff-name-input" className={input} placeholder={t("name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input data-testid="staff-email-input" className={input} placeholder={t("email")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input data-testid="staff-password-input" className={input} placeholder={t("password")} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button data-testid="create-staff-btn" onClick={create} className="h-11 rounded-xl brand-bg text-white text-sm font-medium">{t("addStaff")}</button>
      </div>
      <div className="bg-white rounded-2xl border border-neutral-200 divide-y divide-neutral-100">
        {staff.map((s) => (
          <div key={s.id} data-testid={`staff-row-${s.email}`} className="flex items-center justify-between p-4">
            <div>
              <div className="font-medium">{s.name}</div>
              <div className="text-xs text-neutral-500">{s.email} · {s.role}</div>
            </div>
            <button data-testid={`toggle-staff-${s.email}`} onClick={() => toggle(s)}
              className={`min-h-[40px] px-4 rounded-xl text-xs font-bold ${s.active !== false ? "bg-emerald-100 text-emerald-800" : "bg-neutral-200 text-neutral-600"}`}>
              {s.active !== false ? t("active") : t("inactive")}
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ReportsTab() {
  const { t } = useI18n();
  const { settings } = useSettings();
  const [period, setPeriod] = useState("day");
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/reports", { params: { period } }).then((r) => setData(r.data)); }, [period]);
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
      </div>
    }>
      <div data-testid="report-metrics" className="grid sm:grid-cols-4 gap-4 mb-8">
        {[[t("orders"), data.orders_count], [t("revenue"), money(data.revenue, settings.currency)],
          [t("avgOrder"), money(data.avg_order_value, settings.currency)], ["Lunas", data.paid_count]].map(([l, v]) => (
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

function SettingsTab() {
  const { t } = useI18n();
  const { settings, setSettings, refresh } = useSettings();
  const [f, setF] = useState(settings);
  useEffect(() => setF(settings), [settings]);

  const save = async () => {
    try {
      const { data } = await api.put("/settings", {
        restaurant_name: f.restaurant_name, logo: f.logo, primary_color: f.primary_color,
        currency: f.currency, tax_rate: Number(f.tax_rate), service_charge: Number(f.service_charge),
        table_count: Number(f.table_count),
      });
      setSettings(data); refresh(); toast.success(t("save") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <Panel title={t("settings")}>
      <div className="bg-white rounded-2xl border border-neutral-200 p-6 max-w-xl space-y-4">
        {[["restaurant_name", t("name")], ["logo", "Logo URL"], ["currency", "Currency"]].map(([k, label]) => (
          <div key={k}>
            <label className="text-sm font-medium text-neutral-600">{label}</label>
            <input data-testid={`settings-${k}-input`} className={`${input} mt-1.5`} value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
          </div>
        ))}
        <div>
          <label className="text-sm font-medium text-neutral-600">Warna Utama</label>
          <input data-testid="settings-color-input" type="color" className="mt-1.5 w-20 h-11 rounded-xl border border-neutral-200" value={f.primary_color} onChange={(e) => setF({ ...f, primary_color: e.target.value })} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          {[["tax_rate", t("tax") + " %"], ["service_charge", t("service") + " %"], ["table_count", t("tables")]].map(([k, label]) => (
            <div key={k}>
              <label className="text-sm font-medium text-neutral-600">{label}</label>
              <input data-testid={`settings-${k}-input`} type="number" className={`${input} mt-1.5`} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
            </div>
          ))}
        </div>
        <button data-testid="save-settings-btn" onClick={save} className="w-full h-12 rounded-xl brand-bg text-white font-medium">{t("save")}</button>
      </div>
    </Panel>
  );
}
