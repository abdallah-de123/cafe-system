import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { LogOut, Bell, Clock, PlayCircle, StopCircle, ChefHat, CheckCircle2, Trash2, Plus, Minus } from "lucide-react";
import { api, money, errMsg } from "@/lib/api";
import { useWs } from "@/lib/ws";
import { useAuth } from "@/context/AuthContext";
import { useSettings } from "@/context/SettingsContext";
import { useI18n } from "@/i18n";
import { LangSwitch, StatusBadge } from "@/components/Shared";

const FLOW = ["new", "accepted", "preparing", "ready", "delivered", "closed"];
const nextOf = (s) => FLOW[FLOW.indexOf(s) + 1];
const linePrice = (it) => it.unit_price + (it.options || []).reduce((s, o) => s + (o.price_delta || 0), 0);

export default function CashierDashboard() {
  const { user, logout } = useAuth();
  const { settings } = useSettings();
  const { t } = useI18n();
  const cur = settings.currency;

  const [orders, setOrders] = useState([]);
  const [calls, setCalls] = useState([]);
  const [shift, setShift] = useState(null);
  const [lastShift, setLastShift] = useState(null);
  const [editing, setEditing] = useState(null);

  const load = () => {
    api.get("/orders").then((r) => setOrders(r.data)).catch(() => {});
    api.get("/calls").then((r) => setCalls(r.data)).catch(() => {});
    api.get("/shifts/current").then((r) => setShift(r.data)).catch(() => {});
  };
  useEffect(load, []);

  useWs((event, data) => {
    if (event === "order_created") setOrders((p) => [data, ...p.filter((o) => o.id !== data.id)]);
    if (event === "order_updated")
      setOrders((p) => (p.some((o) => o.id === data.id) ? p.map((o) => (o.id === data.id ? data : o)) : [data, ...p]));
    if (event === "call_created") setCalls((p) => [data, ...p]);
    if (event === "call_updated") setCalls((p) => p.map((c) => (c.id === data.id ? data : c)));
  });

  const visible = orders.filter(
    (o) => user.role === "owner" || o.status === "new" || o.accepted_by === user.id
  );
  const openCalls = calls.filter((c) => c.status === "open");

  const act = async (fn) => {
    try { await fn(); } catch (e) { toast.error(errMsg(e)); }
  };

  const accept = (o) => act(async () => {
    const { data } = await api.post(`/orders/${o.id}/accept`);
    setOrders((p) => p.map((x) => (x.id === o.id ? data : x)));
    toast.success(`${t("accept")} ${o.order_number}`);
  });

  const advance = (o) => act(async () => {
    const { data } = await api.post(`/orders/${o.id}/status`, { status: nextOf(o.status) });
    setOrders((p) => p.map((x) => (x.id === o.id ? data : x)));
    toast.success(`${o.order_number} → ${t(`status_${data.status}`)}`);
  });

  const startShift = () => act(async () => {
    const { data } = await api.post("/shifts/start");
    setShift(data); toast.success(t("startShift"));
  });

  const endShift = () => act(async () => {
    const { data } = await api.post("/shifts/end");
    setShift(null); setLastShift(data);
  });

  const resolveCall = (c) => act(async () => {
    const { data } = await api.post(`/calls/${c.id}/resolve`);
    setCalls((p) => p.map((x) => (x.id === c.id ? data : x)));
  });

  const saveEdit = () => act(async () => {
    const { data } = await api.put(`/orders/${editing.id}/items`, {
      items: editing.items.map((i) => ({
        menu_item_id: i.menu_item_id, name: i.name, qty: i.qty,
        unit_price: i.unit_price, options: i.options || [], note: i.note || "",
      })),
    });
    setOrders((p) => p.map((x) => (x.id === data.id ? data : x)));
    setEditing(null);
    toast.success(t("save") + " ✓");
  });

  return (
    <div className="min-h-screen bg-[#F8F7F4]">
      <header className="bg-[#2E3D36] text-white sticky top-0 z-20">
        <div className="px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl brand-bg grid place-items-center"><ChefHat className="w-5 h-5" /></div>
            <div>
              <div className="font-display font-bold leading-tight">{t("orders")}</div>
              <div className="text-xs text-white/60">{user.name}</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <LangSwitch dark />
            {shift ? (
              <button data-testid="end-shift-btn" onClick={endShift} className="min-h-[44px] px-4 rounded-xl bg-white/10 text-sm font-medium flex items-center gap-2">
                <StopCircle className="w-4 h-4" /> {t("endShift")}
              </button>
            ) : (
              <button data-testid="start-shift-btn" onClick={startShift} className="min-h-[44px] px-4 rounded-xl brand-bg text-sm font-medium flex items-center gap-2">
                <PlayCircle className="w-4 h-4" /> {t("startShift")}
              </button>
            )}
            <button data-testid="logout-btn" onClick={logout} className="w-11 h-11 rounded-xl bg-white/10 grid place-items-center"><LogOut className="w-4 h-4" /></button>
          </div>
        </div>
      </header>

      <main className="p-6 max-w-7xl mx-auto grid lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2">
          <h2 className="font-display font-bold text-xl mb-4">{t("orders")} · {visible.length}</h2>
          {visible.length === 0 && <p data-testid="no-orders" className="text-neutral-500">{t("noOrders")}</p>}
          <div className="grid md:grid-cols-2 gap-4">
            {visible.map((o) => (
              <div key={o.id} data-testid={`order-card-${o.order_number}`} className="bg-white rounded-2xl border border-neutral-200 p-5 rise">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-display font-bold text-lg">{t("table")} {o.table_number}</div>
                    <div className="font-mono text-xs text-neutral-500">{o.order_number}</div>
                  </div>
                  <StatusBadge status={o.status} />
                </div>

                <div className="mt-3 text-sm space-y-1">
                  {o.items.map((it, i) => (
                    <div key={i}>
                      <div className="flex justify-between">
                        <span className="font-medium">{it.qty}× {it.name}</span>
                        <span>{money(linePrice(it) * it.qty, cur)}</span>
                      </div>
                      {it.options?.length > 0 && <div className="text-xs text-neutral-500">{it.options.map((x) => x.label).join(", ")}</div>}
                      {it.note && <div className="text-xs italic text-neutral-400">"{it.note}"</div>}
                    </div>
                  ))}
                </div>

                <div className="mt-3 pt-3 border-t border-neutral-100 flex justify-between font-display font-bold">
                  <span>{t("total")}</span><span>{money(o.total, cur)}</span>
                </div>
                {o.accepted_by_name && (
                  <div className="mt-1 text-xs text-neutral-500">{t("handledBy")}: {o.accepted_by_name}</div>
                )}

                <div className="mt-4 flex gap-2">
                  {o.status === "new" && (
                    <button data-testid={`accept-btn-${o.order_number}`} onClick={() => accept(o)} className="flex-1 min-h-[52px] rounded-xl brand-bg text-white font-medium active:scale-95 transition-transform">
                      {t("accept")}
                    </button>
                  )}
                  {o.status !== "new" && o.status !== "closed" && (
                    <button data-testid={`advance-btn-${o.order_number}`} onClick={() => advance(o)} className="flex-1 min-h-[52px] rounded-xl bg-[#2E3D36] text-white font-medium active:scale-95 transition-transform">
                      {nextOf(o.status) === "closed" ? t("markPaid") : `→ ${t(`status_${nextOf(o.status)}`)}`}
                    </button>
                  )}
                  {o.status === "accepted" && (
                    <button data-testid={`edit-order-btn-${o.order_number}`} onClick={() => setEditing({ ...o, items: o.items.map((x) => ({ ...x })) })} className="min-h-[52px] px-4 rounded-xl border border-neutral-200 font-medium">
                      {t("edit")}
                    </button>
                  )}
                  {o.status === "closed" && (
                    <div className="flex-1 min-h-[52px] rounded-xl bg-neutral-100 text-neutral-500 grid place-items-center text-sm font-medium">
                      <span className="flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> {t("invoice")} {o.order_number}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        <aside className="space-y-6">
          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <h3 className="font-display font-bold text-lg flex items-center gap-2 mb-3">
              <Bell className="w-4 h-4 brand-text" /> {t("calls")} · {openCalls.length}
            </h3>
            {openCalls.length === 0 && <p className="text-sm text-neutral-500">—</p>}
            <div className="space-y-2">
              {openCalls.map((c) => (
                <div key={c.id} data-testid={`call-item-${c.id}`} className="flex items-center justify-between bg-[#F8F7F4] rounded-xl p-3">
                  <div>
                    <div className="font-medium text-sm">{t("table")} {c.table_number}</div>
                    <div className="text-xs text-neutral-500">
                      {c.kind === "help" ? t("needHelp") : c.kind === "bill" ? t("requestBill") : t("cleanTable")}
                    </div>
                  </div>
                  <button data-testid={`resolve-call-${c.id}`} onClick={() => resolveCall(c)} className="min-h-[44px] px-3 rounded-xl brand-bg text-white text-xs font-medium">
                    {t("resolve")}
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-neutral-200 p-5">
            <h3 className="font-display font-bold text-lg flex items-center gap-2 mb-3"><Clock className="w-4 h-4 brand-text" /> {t("shift")}</h3>
            {shift ? (
              <p data-testid="shift-active" className="text-sm text-neutral-600">
                {t("startShift")}: {new Date(shift.started_at).toLocaleTimeString()}
              </p>
            ) : (
              <p className="text-sm text-neutral-500">—</p>
            )}
            {lastShift && (
              <div data-testid="shift-summary" className="mt-3 text-sm bg-[#F8F7F4] rounded-xl p-3 space-y-1">
                <div className="flex justify-between"><span>{t("ordersCount")}</span><b>{lastShift.orders_count}</b></div>
                <div className="flex justify-between"><span>{t("totalCash")}</span><b>{money(lastShift.total_cash, cur)}</b></div>
              </div>
            )}
          </div>
        </aside>
      </main>

      {editing && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" onClick={() => setEditing(null)}>
          <div data-testid="edit-order-modal" className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display font-bold text-xl mb-1">{t("edit")} {editing.order_number}</h3>
            <p className="text-xs text-neutral-500 mb-4">Jendela edit 60 detik setelah diterima.</p>
            <div className="space-y-3">
              {editing.items.map((it, i) => (
                <div key={i} className="flex items-center gap-3 border-b border-neutral-100 pb-2">
                  <span className="flex-1 text-sm font-medium">{it.name}</span>
                  <button data-testid={`edit-dec-${i}`} onClick={() => setEditing((p) => ({ ...p, items: p.items.map((x, j) => (j === i ? { ...x, qty: Math.max(1, x.qty - 1) } : x)) }))} className="w-10 h-10 rounded-lg border grid place-items-center"><Minus className="w-4 h-4" /></button>
                  <span className="w-6 text-center font-bold">{it.qty}</span>
                  <button data-testid={`edit-inc-${i}`} onClick={() => setEditing((p) => ({ ...p, items: p.items.map((x, j) => (j === i ? { ...x, qty: x.qty + 1 } : x)) }))} className="w-10 h-10 rounded-lg border grid place-items-center"><Plus className="w-4 h-4" /></button>
                  <button data-testid={`edit-remove-${i}`} onClick={() => setEditing((p) => ({ ...p, items: p.items.filter((_, j) => j !== i) }))} className="w-10 h-10 rounded-lg grid place-items-center text-red-500"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
            <div className="mt-5 flex gap-3">
              <button data-testid="cancel-edit-btn" onClick={() => setEditing(null)} className="flex-1 h-12 rounded-xl border border-neutral-200 font-medium">{t("cancel")}</button>
              <button data-testid="save-edit-btn" onClick={saveEdit} className="flex-1 h-12 rounded-xl brand-bg text-white font-medium">{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
