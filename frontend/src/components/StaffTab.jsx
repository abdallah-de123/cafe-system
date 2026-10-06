// Staff screen: list, add, rename, deactivate/reactivate, reset password, delete.
// The backend enforces the rules; here we only hide actions that would certainly fail.
import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2, KeyRound, Pencil } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useI18n } from "@/i18n";

const input = "w-full h-11 px-4 rounded-xl bg-white border border-neutral-200 outline-none focus:border-[color:var(--brand)] text-sm";

export function StaffTab({ Panel }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const [staff, setStaff] = useState([]);
  const blank = { name: "", email: "", password: "", role: "cashier" };
  const [form, setForm] = useState(blank);
  const [editing, setEditing] = useState(null); // { id, name, password }

  const load = () => api.get("/staff").then((r) => setStaff(r.data)).catch((e) => toast.error(errMsg(e)));
  useEffect(() => { load(); }, []);

  const run = async (fn, ok) => {
    try { await fn(); load(); if (ok) toast.success(ok); } catch (e) { toast.error(errMsg(e)); }
  };

  const create = () => run(async () => { await api.post("/staff", form); setForm(blank); }, t("addStaff") + " ✓");
  const toggle = (s) => {
    const active = s.active !== false;
    if (active && !window.confirm(t("deactivateConfirm"))) return;
    run(() => api.put(`/staff/${s.id}`, { active: !active }));
  };
  const remove = (s) => {
    if (!window.confirm(t("deleteStaffConfirm"))) return;
    run(async () => {
      const { data } = await api.delete(`/staff/${s.id}`);
      toast.success(data.mode === "deleted" ? t("staffDeleted") : t("staffAnonymized"));
    });
  };
  const saveEdit = () => run(async () => {
    const body = { name: editing.name };
    if (editing.password) body.password = editing.password;
    await api.put(`/staff/${editing.id}`, body);
    setEditing(null);
  }, t("save") + " ✓");

  // Roles the current user may create.
  const creatable = user.role === "super_admin" ? ["cashier", "owner", "super_admin"] : ["cashier"];

  return (
    <Panel title={t("staff")}>
      <div className="bg-white rounded-2xl border border-neutral-200 p-5 mb-6 grid sm:grid-cols-5 gap-3">
        <input data-testid="staff-name-input" className={input} placeholder={t("name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input data-testid="staff-email-input" type="email" className={input} placeholder={t("email")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input data-testid="staff-password-input" type="password" className={input} placeholder={t("password")} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <select data-testid="staff-role-select" className={input} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          {creatable.map((r) => <option key={r} value={r}>{t(`role_${r}`)}</option>)}
        </select>
        <button data-testid="create-staff-btn" onClick={create} className="h-11 rounded-xl brand-bg text-white text-sm font-medium">{t("addStaff")}</button>
      </div>

      <div className="bg-white rounded-2xl border border-neutral-200 divide-y divide-neutral-100">
        {staff.map((s) => {
          const self = s.id === user.id;
          const active = s.active !== false;
          return (
            <div key={s.id} data-testid={`staff-row-${s.email}`} className="flex flex-wrap items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <div className="font-medium flex items-center gap-2">
                  {s.name} {self && <span className="text-[10px] px-2 py-0.5 rounded-full bg-neutral-100 text-neutral-600">{t("you")}</span>}
                </div>
                <div className="text-xs text-neutral-500">{s.email} · {t(`role_${s.role}`)}</div>
              </div>
              <div className="flex items-center gap-2">
                <button data-testid={`edit-staff-${s.email}`} onClick={() => setEditing({ id: s.id, name: s.name, password: "" })} title={t("edit")}
                  className="w-10 h-10 rounded-xl border border-neutral-200 grid place-items-center"><Pencil className="w-4 h-4" /></button>
                <button data-testid={`toggle-staff-${s.email}`} onClick={() => toggle(s)} disabled={self}
                  className={`min-h-[40px] px-4 rounded-xl text-xs font-bold disabled:opacity-40 ${active ? "bg-emerald-100 text-emerald-800" : "bg-neutral-200 text-neutral-600"}`}>
                  {active ? t("active") : t("inactive")}
                </button>
                <button data-testid={`delete-staff-${s.email}`} onClick={() => remove(s)} disabled={self} title={t("deleteStaff")}
                  className="w-10 h-10 rounded-xl border border-neutral-200 grid place-items-center text-red-500 disabled:opacity-40"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          );
        })}
      </div>

      {editing && (
        <div className="fixed inset-0 z-40 bg-black/40 grid place-items-center p-4" onClick={() => setEditing(null)}>
          <div data-testid="edit-staff-modal" className="bg-white rounded-2xl p-6 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-display font-bold text-xl mb-4">{t("edit")}</h3>
            <div className="space-y-3">
              <input data-testid="edit-staff-name-input" className={input} placeholder={t("name")} value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <div className="relative">
                <KeyRound className="w-4 h-4 absolute top-3.5 start-3.5 text-neutral-400" />
                <input data-testid="edit-staff-password-input" type="password" className={`${input} ps-10`} placeholder={t("resetPassword")} value={editing.password} onChange={(e) => setEditing({ ...editing, password: e.target.value })} />
              </div>
            </div>
            <div className="mt-5 flex gap-3">
              <button data-testid="edit-staff-cancel-btn" onClick={() => setEditing(null)} className="flex-1 h-12 rounded-xl border border-neutral-200 font-medium">{t("cancel")}</button>
              <button data-testid="edit-staff-save-btn" onClick={saveEdit} className="flex-1 h-12 rounded-xl brand-bg text-white font-medium">{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}
