import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { Search, ShoppingBag, Plus, Minus, X, HandHelping, Receipt, Sparkles, Star, ChefHat, CheckCircle2 } from "lucide-react";
import { api, money, errMsg } from "@/lib/api";
import { useWs } from "@/lib/ws";
import { useSettings } from "@/context/SettingsContext";
import { useI18n, localized } from "@/i18n";
import { LangSwitch, StatusTracker, StatusBadge } from "@/components/Shared";

const linePrice = (it) => it.unit_price + (it.options || []).reduce((s, o) => s + (o.price_delta || 0), 0);

export default function CustomerMenu() {
  const { tableNumber } = useParams();
  const table = Number(tableNumber);
  const { settings } = useSettings();
  const { t, lang } = useI18n();
  const cur = settings.currency;

  const [items, setItems] = useState([]);
  const [cats, setCats] = useState([]);
  const [placed, setPlaced] = useState(null);
  const [cat, setCat] = useState("all");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const [cart, setCart] = useState([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [orders, setOrders] = useState([]);
  const [rated, setRated] = useState({});
  const [ratingFor, setRatingFor] = useState(null);

  const loadMenu = () => {
    api.get("/menu", { params: { include_unavailable: true } }).then((r) => setItems(r.data));
    api.get("/categories").then((r) => setCats(r.data)).catch(() => {});
  };
  const loadOrders = () => api.get(`/tables/${table}/orders`).then((r) => setOrders(r.data));

  useEffect(() => { loadMenu(); loadOrders(); }, [table]);

  useWs((event, data) => {
    if (event === "menu_updated") loadMenu();
    if (event === "order_updated" && data.table_number === table)
      setOrders((prev) => prev.map((o) => (o.id === data.id ? data : o)));
  });

  const catList = useMemo(
    () => [{ name: "all" }, ...cats.filter((c) => items.some((i) => i.category === c.name))],
    [cats, items]
  );
  const ql = q.toLowerCase();
  const shown = items.filter(
    (i) =>
      (cat === "all" || i.category === cat) &&
      (i.name.toLowerCase().includes(ql) ||
        (i.name_en || "").toLowerCase().includes(ql) ||
        (i.name_ar || "").includes(q))
  );
  const cartTotal = cart.reduce((s, it) => s + linePrice(it) * it.qty, 0);
  const cartCount = cart.reduce((s, it) => s + it.qty, 0);

  const submit = async () => {
    try {
      const payload = {
        table_number: table,
        items: cart.map((c) => ({
          menu_item_id: c.menu_item_id, name: c.name, qty: c.qty,
          unit_price: c.unit_price, options: c.options, note: c.note,
        })),
      };
      const { data } = await api.post("/orders", payload);
      setCart([]); setCartOpen(false);
      setOrders((p) => [data, ...p]);
      setPlaced(data);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const call = async (kind) => {
    try {
      await api.post("/calls", { table_number: table, kind });
      toast.success(t("callWaiter") + " ✓");
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div className="min-h-screen bg-[#F8F7F4] pb-28">
      <header className="glass sticky top-0 z-30 border-b border-black/5">
        <div className="px-5 pt-4 pb-3 max-w-2xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl brand-bg grid place-items-center">
                <ChefHat className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="font-display font-bold leading-tight">{settings.restaurant_name}</div>
                <div data-testid="table-label" className="text-xs text-neutral-500">{t("table")} {table}</div>
              </div>
            </div>
            <LangSwitch />
          </div>

          <div className="mt-3 relative">
            <Search className="w-4 h-4 absolute top-3.5 start-3.5 text-neutral-400" />
            <input
              data-testid="menu-search-input" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={t("search")}
              className="w-full h-11 ps-10 pe-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] transition-colors text-sm"
            />
          </div>

          <div className="mt-3 flex gap-2 overflow-x-auto no-scrollbar">
            {catList.map((c) => (
              <button
                key={c.name} data-testid={`category-${c.name}`} onClick={() => setCat(c.name)}
                className={`shrink-0 px-4 py-2 rounded-full text-sm font-medium border transition-colors duration-200 ${
                  cat === c.name ? "brand-bg text-white border-transparent" : "bg-white text-[#2E3D36] border-neutral-200"
                }`}
              >
                {c.name === "all" ? t("all") : localized(c, "name", lang)}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-5 pt-5">
        {orders.length > 0 && (
          <section className="mb-7">
            <h2 className="font-display font-bold text-lg mb-3">{t("myOrders")}</h2>
            <div className="space-y-3">
              {orders.slice(0, 3).map((o) => (
                <div key={o.id} data-testid={`my-order-${o.order_number}`} className="bg-white rounded-2xl border border-neutral-200 p-4 soft-shadow rise">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs text-neutral-500">{o.order_number}</span>
                    <StatusBadge status={o.status} />
                  </div>
                  <StatusTracker status={o.status} />
                  <div className="mt-4 pt-3 border-t border-neutral-100 text-sm space-y-1">
                    {o.items.map((it, i) => (
                      <div key={i} className="flex justify-between text-neutral-600">
                        <span>{it.qty}× {localized(it, "name", lang)}</span>
                        <span>{money(linePrice(it) * it.qty, cur)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between text-neutral-500 pt-1"><span>{t("subtotal")}</span><span>{money(o.subtotal, cur)}</span></div>
                    <div className="flex justify-between text-neutral-500"><span>{t("tax")} {o.tax_rate}%</span><span>{money(o.tax, cur)}</span></div>
                    <div className="flex justify-between text-neutral-500"><span>{t("service")} {o.service_rate}%</span><span>{money(o.service, cur)}</span></div>
                    <div className="flex justify-between font-display font-bold text-base pt-1"><span>{t("total")}</span><span>{money(o.total, cur)}</span></div>
                  </div>
                  {["delivered", "closed"].includes(o.status) && !rated[o.id] && (
                    <button
                      data-testid={`rate-order-btn-${o.order_number}`} onClick={() => setRatingFor(o)}
                      className="mt-3 w-full h-11 rounded-xl border brand-border brand-text font-medium text-sm active:scale-95 transition-transform"
                    >
                      {t("rateOrder")}
                    </button>
                  )}
                  {rated[o.id] && <p className="mt-3 text-xs text-emerald-700">{t("thanks")}</p>}
                  {o.status === "closed" && (
                    <a
                      data-testid={`view-invoice-link-${o.order_number}`} href={`/invoice/${o.id}`} target="_blank" rel="noreferrer"
                      className="mt-3 w-full h-11 rounded-xl bg-[#2E3D36] text-white font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                    >
                      <Receipt className="w-4 h-4" /> {t("viewInvoice")}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="flex gap-2 mb-6">
          {[["help", HandHelping, t("needHelp")], ["bill", Receipt, t("requestBill")], ["clean", Sparkles, t("cleanTable")]].map(
            ([kind, Icon, label]) => (
              <button
                key={kind} data-testid={`call-${kind}-btn`} onClick={() => call(kind)}
                className="flex-1 min-h-[52px] rounded-xl bg-white border border-neutral-200 text-xs font-medium flex flex-col items-center justify-center gap-1 hover:border-[color:var(--brand)] transition-colors"
              >
                <Icon className="w-4 h-4 brand-text" /> {label}
              </button>
            )
          )}
        </div>

        <h2 className="font-display font-bold text-lg mb-3">{t("menu")}</h2>
        <div className="grid grid-cols-2 gap-4">
          {shown.map((it, idx) => (
            <button
              key={it.id} data-testid={`menu-item-${it.id}`} disabled={!it.available}
              onClick={() => setSel({ item: it, qty: 1, note: "", chosen: {} })}
              className="text-start bg-white rounded-2xl border border-neutral-200 overflow-hidden soft-shadow hover:-translate-y-1 transition-transform duration-300 disabled:opacity-50 rise"
              style={{ animationDelay: `${idx * 40}ms` }}
            >
              <img src={it.image} alt={localized(it, "name", lang)} className="w-full h-32 object-cover" />
              <div className="p-3">
                <div className="font-display font-bold text-sm leading-tight">{localized(it, "name", lang)}</div>
                <p className="text-xs text-neutral-500 mt-1 line-clamp-2">{localized(it, "description", lang)}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="font-bold text-sm brand-text">{money(it.discount_price ?? it.price, cur)}</span>
                  {it.discount_price && <span className="text-xs text-neutral-400 line-through">{money(it.price, cur)}</span>}
                </div>
                {!it.available && <div className="text-[10px] text-red-600 mt-1">Habis</div>}
              </div>
            </button>
          ))}
        </div>
      </main>

      {cartCount > 0 && (
        <div className="fixed bottom-0 inset-x-0 z-30 p-4 glass border-t border-black/5">
          <button
            data-testid="open-cart-btn" onClick={() => setCartOpen(true)}
            className="max-w-2xl mx-auto w-full h-14 rounded-2xl brand-bg text-white flex items-center justify-between px-5 active:scale-95 transition-transform duration-200 pulse-ring"
          >
            <span className="flex items-center gap-2 font-medium"><ShoppingBag className="w-5 h-5" /> {t("cart")} · {cartCount}</span>
            <span className="font-display font-bold">{money(cartTotal, cur)}</span>
          </button>
        </div>
      )}

      {sel && <ItemSheet sel={sel} setSel={setSel} cur={cur} onAdd={(entry) => { setCart((p) => [...p, entry]); setSel(null); toast.success(t("addToCart") + " ✓"); }} />}

      {cartOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 flex items-end" onClick={() => setCartOpen(false)}>
          <div data-testid="cart-sheet" className="bg-white w-full max-w-2xl mx-auto rounded-t-3xl p-5 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display font-bold text-xl">{t("cart")}</h3>
              <button data-testid="close-cart-btn" onClick={() => setCartOpen(false)}><X className="w-5 h-5" /></button>
            </div>
            {cart.length === 0 && <p className="text-neutral-500 text-sm">{t("emptyCart")}</p>}
            <div className="space-y-3">
              {cart.map((c, i) => (
                <div key={i} className="flex gap-3 items-start border-b border-neutral-100 pb-3">
                  <div className="flex-1">
                    <div className="font-medium text-sm">{localized(c, "name", lang)}</div>
                    {c.options.length > 0 && <div className="text-xs text-neutral-500">{c.options.map((o) => localized(o, "label", lang)).join(", ")}</div>}
                    {c.note && <div className="text-xs italic text-neutral-400">"{c.note}"</div>}
                    <div className="text-sm brand-text font-bold mt-1">{money(linePrice(c) * c.qty, cur)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button data-testid={`cart-dec-${i}`} onClick={() => setCart((p) => p.map((x, j) => (j === i ? { ...x, qty: Math.max(1, x.qty - 1) } : x)))} className="w-9 h-9 rounded-lg border border-neutral-200 grid place-items-center"><Minus className="w-4 h-4" /></button>
                    <span className="w-6 text-center text-sm font-bold">{c.qty}</span>
                    <button data-testid={`cart-inc-${i}`} onClick={() => setCart((p) => p.map((x, j) => (j === i ? { ...x, qty: x.qty + 1 } : x)))} className="w-9 h-9 rounded-lg border border-neutral-200 grid place-items-center"><Plus className="w-4 h-4" /></button>
                    <button data-testid={`cart-remove-${i}`} onClick={() => setCart((p) => p.filter((_, j) => j !== i))} className="w-9 h-9 rounded-lg grid place-items-center text-red-500"><X className="w-4 h-4" /></button>
                  </div>
                </div>
              ))}
            </div>
            {cart.length > 0 && (
              <button data-testid="submit-order-btn" onClick={submit} className="mt-5 w-full h-14 rounded-2xl brand-bg text-white font-medium active:scale-95 transition-transform">
                {t("submitOrder")} · {money(cartTotal, cur)}
              </button>
            )}
          </div>
        </div>
      )}

      {placed && (
        <div className="fixed inset-0 z-50 bg-black/50 grid place-items-center p-5" onClick={() => setPlaced(null)}>
          <div data-testid="order-confirmation" className="bg-white rounded-3xl p-7 w-full max-w-sm text-center rise" onClick={(e) => e.stopPropagation()}>
            <div className="w-16 h-16 rounded-full brand-bg grid place-items-center mx-auto">
              <CheckCircle2 className="w-9 h-9 text-white" />
            </div>
            <h3 className="font-display font-bold text-2xl mt-5">{t("orderPlaced")}</h3>
            <p className="text-sm text-neutral-500 mt-2">{t("orderPlacedDesc")}</p>
            <div className="mt-5 bg-[#F8F7F4] rounded-2xl p-4">
              <div className="text-xs text-neutral-500">{t("orderNumber")}</div>
              <div data-testid="confirmation-order-number" className="font-mono font-bold text-lg">{placed.order_number}</div>
              <div className="mt-2 flex justify-between text-sm"><span>{t("total")}</span><b>{money(placed.total, cur)}</b></div>
            </div>
            <button
              data-testid="confirmation-close-btn" onClick={() => setPlaced(null)}
              className="mt-5 w-full h-12 rounded-xl brand-bg text-white font-medium active:scale-95 transition-transform"
            >
              {t("trackOrder")}
            </button>
          </div>
        </div>
      )}

      {ratingFor && (
        <RatingSheet
          order={ratingFor} onClose={() => setRatingFor(null)}
          onDone={(id) => { setRated((p) => ({ ...p, [id]: true })); setRatingFor(null); toast.success(t("thanks")); }}
        />
      )}
    </div>
  );
}

function ItemSheet({ sel, setSel, cur, onAdd }) {
  const { t, lang } = useI18n();
  const { item, qty, note, chosen } = sel;
  const options = Object.values(chosen).filter(Boolean);
  const base = item.discount_price ?? item.price;
  const unitTotal = base + options.reduce((s, o) => s + (o.price_delta || 0), 0);
  const missing = (item.options || []).some((g) => g.required && !chosen[g.name]);

  return (
    <div className="fixed inset-0 z-40 bg-black/40 flex items-end" onClick={() => setSel(null)}>
      <div data-testid="item-sheet" className="bg-white w-full max-w-2xl mx-auto rounded-t-3xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <img src={item.image} alt={localized(item, "name", lang)} className="w-full h-44 object-cover" />
        <div className="p-5">
          <div className="flex items-start justify-between">
            <h3 className="font-display font-bold text-2xl leading-tight">{localized(item, "name", lang)}</h3>
            <button data-testid="close-item-btn" onClick={() => setSel(null)}><X className="w-5 h-5" /></button>
          </div>
          <p className="text-sm text-neutral-500 mt-2">{localized(item, "description", lang)}</p>

          {(item.options || []).map((g) => (
            <div key={g.name} className="mt-5">
              <div className="text-sm font-bold mb-2">{localized(g, "name", lang)} {g.required && <span className="brand-text">*</span>}</div>
              <div className="flex flex-wrap gap-2">
                {g.choices.map((c) => {
                  const active = chosen[g.name]?.label === c.label;
                  return (
                    <button
                      key={c.label} data-testid={`option-${g.name}-${c.label}`}
                      onClick={() => setSel((s) => ({ ...s, chosen: { ...s.chosen, [g.name]: active && !g.required ? null : { ...c, group: g.name } } }))}
                      className={`min-h-[44px] px-4 rounded-xl text-sm font-medium border transition-colors ${
                        active ? "brand-bg text-white border-transparent" : "bg-white border-neutral-200"
                      }`}
                    >
                      {localized(c, "label", lang)}{c.price_delta ? ` +${money(c.price_delta, cur)}` : ""}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="mt-5">
            <div className="text-sm font-bold mb-2">{t("note")}</div>
            <input
              data-testid="item-note-input" value={note} placeholder={t("notePh")}
              onChange={(e) => setSel((s) => ({ ...s, note: e.target.value }))}
              className="w-full h-11 px-4 rounded-xl bg-[#F8F7F4] border border-neutral-200 outline-none text-sm focus:border-[color:var(--brand)]"
            />
          </div>

          <div className="mt-5 flex items-center gap-4">
            <div className="flex items-center gap-2">
              <button data-testid="item-qty-dec" onClick={() => setSel((s) => ({ ...s, qty: Math.max(1, s.qty - 1) }))} className="w-11 h-11 rounded-xl border border-neutral-200 grid place-items-center"><Minus className="w-4 h-4" /></button>
              <span data-testid="item-qty" className="w-8 text-center font-bold">{qty}</span>
              <button data-testid="item-qty-inc" onClick={() => setSel((s) => ({ ...s, qty: s.qty + 1 }))} className="w-11 h-11 rounded-xl border border-neutral-200 grid place-items-center"><Plus className="w-4 h-4" /></button>
            </div>
            <button
              data-testid="add-to-cart-btn" disabled={missing}
              onClick={() => onAdd({
                menu_item_id: item.id, name: item.name, name_en: item.name_en, name_ar: item.name_ar,
                qty, unit_price: base, note,
                options: options.map(({ label, label_en, label_ar, price_delta }) => ({ label, label_en, label_ar, price_delta })),
              })}
              className="flex-1 h-12 rounded-xl brand-bg text-white font-medium active:scale-95 transition-transform disabled:opacity-50"
            >
              {t("addToCart")} · {money(unitTotal * qty, cur)}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RatingSheet({ order, onClose, onDone }) {
  const { t } = useI18n();
  const [v, setV] = useState({ food: 5, service: 5, speed: 5 });
  const [comment, setComment] = useState("");
  const send = async () => {
    try {
      await api.post("/ratings", { order_id: order.id, ...v, comment });
      onDone(order.id);
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end" onClick={onClose}>
      <div data-testid="rating-sheet" className="bg-white w-full max-w-2xl mx-auto rounded-t-3xl p-5" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-display font-bold text-xl mb-4">{t("rateOrder")}</h3>
        {[["food", t("food")], ["service", t("serviceR")], ["speed", t("speed")]].map(([k, label]) => (
          <div key={k} className="flex items-center justify-between py-2">
            <span className="text-sm font-medium">{label}</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} data-testid={`rate-${k}-${n}`} onClick={() => setV((p) => ({ ...p, [k]: n }))}>
                  <Star className={`w-7 h-7 ${n <= v[k] ? "fill-[color:var(--brand)] text-[color:var(--brand)]" : "text-neutral-300"}`} />
                </button>
              ))}
            </div>
          </div>
        ))}
        <input
          data-testid="rating-comment-input" value={comment} onChange={(e) => setComment(e.target.value)}
          placeholder={t("note")} className="mt-3 w-full h-11 px-4 rounded-xl bg-[#F8F7F4] border border-neutral-200 outline-none text-sm"
        />
        <button data-testid="send-rating-btn" onClick={send} className="mt-4 w-full h-12 rounded-xl brand-bg text-white font-medium active:scale-95 transition-transform">
          {t("sendRating")}
        </button>
      </div>
    </div>
  );
}
