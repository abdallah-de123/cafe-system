import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Printer, ChefHat } from "lucide-react";
import { api, money } from "@/lib/api";
import { useSettings } from "@/context/SettingsContext";
import { useI18n, localized } from "@/i18n";

const linePrice = (it) => it.unit_price + (it.options || []).reduce((s, o) => s + (o.price_delta || 0), 0);

export default function Invoice() {
  const { orderId } = useParams();
  const { settings } = useSettings();
  const { t, lang } = useI18n();
  const [o, setO] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get(`/orders/${orderId}`).then((r) => setO(r.data)).catch(() => setErr("Not found"));
  }, [orderId]);

  if (err) return <div data-testid="invoice-error" className="p-10 text-center text-neutral-500">{err}</div>;
  if (!o) return <div className="p-10 text-center text-neutral-500">...</div>;
  const cur = o.currency || settings.currency;

  return (
    <div className="min-h-screen bg-[#F8F7F4] py-8 px-4 print:bg-white print:p-0">
      <style>{`@media print { .no-print { display:none !important } body { background:#fff } }`}</style>
      <div data-testid="invoice-page" className="max-w-sm mx-auto bg-white rounded-2xl border border-neutral-200 p-6 print:border-0 print:rounded-none">
        <div className="text-center mb-5">
          {settings.logo ? (
            <img src={settings.logo} alt="" className="w-14 h-14 rounded-xl object-cover mx-auto mb-2" />
          ) : (
            <div className="w-12 h-12 rounded-xl brand-bg text-white grid place-items-center mx-auto mb-2"><ChefHat className="w-6 h-6" /></div>
          )}
          <h1 className="font-display font-bold text-xl">{settings.restaurant_name}</h1>
          <div className="text-xs text-neutral-500 mt-1">{t("invoice")}</div>
          <div data-testid="invoice-number" className="font-mono font-bold text-sm mt-1">{o.order_number}</div>
          <div className="text-xs text-neutral-500">
            {t("table")} {o.table_number} · {new Date(o.created_at).toLocaleString()}
          </div>
        </div>

        <div className="border-t border-dashed border-neutral-300 pt-3 text-sm space-y-2">
          {o.items.map((it, i) => (
            <div key={i}>
              <div className="flex justify-between">
                <span>{it.qty}× {localized(it, "name", lang)}</span>
                <span>{money(linePrice(it) * it.qty, cur)}</span>
              </div>
              {it.options?.length > 0 && <div className="text-xs text-neutral-500 ps-4">{it.options.map((x) => x.label).join(", ")}</div>}
            </div>
          ))}
        </div>

        <div className="border-t border-dashed border-neutral-300 mt-3 pt-3 text-sm space-y-1">
          <div className="flex justify-between text-neutral-600"><span>{t("subtotal")}</span><span>{money(o.subtotal, cur)}</span></div>
          <div className="flex justify-between text-neutral-600"><span>{t("tax")} {o.tax_rate}%</span><span>{money(o.tax, cur)}</span></div>
          <div className="flex justify-between text-neutral-600"><span>{t("service")} {o.service_rate}%</span><span>{money(o.service, cur)}</span></div>
          <div data-testid="invoice-total" className="flex justify-between font-display font-bold text-lg pt-2 border-t border-neutral-200 mt-2">
            <span>{t("total")}</span><span>{money(o.total, cur)}</span>
          </div>
        </div>

        <div className="mt-4 text-center text-xs text-neutral-500">
          {o.status === "closed" ? t("paidStamp") : t(`status_${o.status}`)}
          {o.accepted_by_name && <div>{t("handledBy")}: {o.accepted_by_name}</div>}
          <div className="mt-2">{t("thanksVisit")}</div>
        </div>

        <button
          data-testid="print-invoice-btn" onClick={() => window.print()}
          className="no-print mt-6 w-full h-12 rounded-xl brand-bg text-white font-medium flex items-center justify-center gap-2 active:scale-95 transition-transform"
        >
          <Printer className="w-4 h-4" /> {t("printInvoice")}
        </button>
      </div>
    </div>
  );
}
