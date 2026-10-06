import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Ban } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useWs } from "@/lib/ws";
import { useI18n, localized } from "@/i18n";

export const SoldOutPanel = () => {
  const { t, lang } = useI18n();
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");

  const load = () => api.get("/menu", { params: { include_unavailable: true } }).then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  useWs((event) => { if (event === "menu_updated") load(); });

  const toggle = async (it) => {
    try {
      const { data } = await api.patch(`/menu/${it.id}/availability`, { available: !it.available });
      setItems((p) => p.map((x) => (x.id === it.id ? data : x)));
      toast.success(`${localized(it, "name", lang)}: ${data.available ? t("available") : t("soldOut")}`);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const shown = items.filter((it) => !q || localized(it, "name", lang).toLowerCase().includes(q.toLowerCase()));
  const soldOut = items.filter((it) => !it.available).length;

  return (
    <div data-testid="sold-out-panel" className="bg-white rounded-2xl border border-neutral-200 p-5">
      <h3 className="font-display font-bold text-lg flex items-center gap-2 mb-3">
        <Ban className="w-4 h-4 brand-text" /> {t("soldOutPanel")} {soldOut > 0 && <span className="text-xs font-medium text-red-600">· {soldOut} {t("soldOut")}</span>}
      </h3>
      <input
        data-testid="sold-out-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")}
        className="w-full h-10 px-3 rounded-xl border border-neutral-200 text-sm mb-3 bg-[#F8F7F4]"
      />
      <div className="space-y-1.5 max-h-80 overflow-y-auto pe-1">
        {shown.map((it) => (
          <div key={it.id} className="flex items-center justify-between gap-2 py-1.5 border-b border-neutral-100 last:border-0">
            <span className={`text-sm truncate ${it.available ? "" : "line-through text-neutral-400"}`}>{localized(it, "name", lang)}</span>
            <button
              data-testid={`sold-out-toggle-${it.id}`} onClick={() => toggle(it)} role="switch" aria-checked={it.available}
              className={`shrink-0 min-h-[36px] px-3 rounded-full text-xs font-bold transition-colors duration-200 ${
                it.available ? "bg-emerald-100 text-emerald-800" : "bg-red-600 text-white"
              }`}
            >
              {it.available ? t("available") : t("soldOut")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
