"""Settings routes: public read, manager update, super-admin-only section."""
from fastapi import APIRouter, Depends
import secrets

from core.audit import audit
from core.db import db
from core.security import require_manager, require_super_admin
from core.settings import SettingsIn, AdminSettingsIn, get_settings_doc, get_admin_settings
from core.ws import manager
from core.uploads import cleanup_image_if_unused, thumbnail_url
from core.inventory import refresh_inventory_alerts, restore_inventory_auto_hidden_items, sync_menu_availability
from core.reporting import business_range
from core.billing import refresh_prepaid_balance
from models import BillingTopUpIn, BillingMonthPaymentIn

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def read_settings():
    """Public settings (branding, currency, languages, tax...). Never includes admin settings."""
    return await get_settings_doc()


@router.put("/settings")
async def update_settings(body: SettingsIn, user: dict = Depends(require_manager)):
    """Owner/super admin updates public settings. Only provided (non-null) keys change."""
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    old_settings = await db.settings.find_one({"key": "main"}) or {}
    old_logo = old_settings.get("logo", "")
    if "logo" in upd:
        # Always pair a logo with the thumbnail generated for that exact uploaded image.
        upd["logo_thumbnail"] = thumbnail_url(upd["logo"])
    if upd:
        await db.settings.update_one({"key": "main"}, {"$set": upd}, upsert=True)
        shown = {k: ("***" if k == "wifi_password" else v) for k, v in upd.items()}
        await audit(user, "settings.update", ", ".join(f"{k}={v}" for k, v in shown.items()))
    if "logo" in upd and old_logo and old_logo != upd["logo"]:
        await cleanup_image_if_unused(old_logo)
    s = await get_settings_doc()
    if "alert_in_app" in upd or "default_low_stock_threshold" in upd:
        await refresh_inventory_alerts()
    if upd.get("auto_hide_out_of_stock") is False:
        await restore_inventory_auto_hidden_items()
    elif upd.get("auto_hide_out_of_stock") is True:
        await sync_menu_availability()
    await manager.broadcast("settings_updated", s)
    return s


@router.get("/admin/settings")
async def read_admin_settings(user: dict = Depends(require_super_admin)):
    """Super admin: license, feature flags, billing configuration."""
    return await get_admin_settings()


@router.put("/admin/settings")
async def update_admin_settings(body: AdminSettingsIn, user: dict = Depends(require_super_admin)):
    """Super admin updates the hidden settings."""
    upd = {f"admin.{k}": v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.settings.update_one({"key": "main"}, {"$set": upd}, upsert=True)
        await audit(user, "settings.admin_update", ", ".join(f"{k}={v}" for k, v in upd.items()))
    return await get_admin_settings()


@router.get("/billing/summary")
async def owner_billing_summary(user: dict = Depends(require_manager)):
    """Expose the owner's current invoice fee and prepaid balance without admin settings."""
    admin = await get_admin_settings()
    settings = await get_settings_doc()
    start, end, first, _ = business_range(settings, "month")
    mode = admin["billing_mode"]
    rows = await db.billing_ledger.aggregate([
        {"$match": {"closed_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}, "mode": mode}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "amount": {"$sum": "$fee"}}},
    ]).to_list(1)
    count = int(rows[0]["count"]) if rows else 0
    amount = round(float(rows[0]["amount"]), 2) if rows and mode == "monthly" else 0
    refunds = await db.invoice_reversals.aggregate([
        {"$match": {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}},
        {"$group": {"_id": None, "amount": {"$sum": "$fee_refund"}}},
    ]).to_list(1)
    if refunds and mode == "monthly":
        amount = max(0.0, round(amount - float(refunds[0]["amount"]), 2))
    account = await db.billing_accounts.find_one({"_id": "main"}) or {"balance": 0}
    payment = await db.billing_month_payments.find_one({"month": first})
    return {"mode": admin["billing_mode"], "month": first, "currency": settings["currency"],
            "fee_per_invoice": admin["fee_per_invoice"], "invoice_count": count, "amount_due": amount,
            "monthly_paid": bool(payment and payment.get("paid", True)), "balance": round(float(account.get("balance", 0)), 2),
            "warning": mode == "prepaid" and float(account.get("balance", 0)) <= float(admin["low_balance_warning"])}


@router.get("/admin/billing/usage")
async def billing_usage(user: dict = Depends(require_super_admin)):
    """Show this copy's current-month billing rows, grouped by day, without exposing mutations."""
    settings = await get_settings_doc()
    admin = await get_admin_settings()
    start, end, month, _ = business_range(settings, "month")
    match = {"closed_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}, "mode": admin["billing_mode"]}
    days = await db.billing_ledger.aggregate([
        {"$match": match},
        {"$addFields": {"_closed": {"$dateFromString": {"dateString": "$closed_at", "onError": None}}}},
        {"$group": {"_id": {"$dateToString": {"date": "$_closed", "format": "%Y-%m-%d", "timezone": settings["timezone"]}},
                    "count": {"$sum": 1}, "fees": {"$sum": "$fee"}, "tax": {"$sum": "$fee_tax"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(40)
    count = await db.billing_ledger.count_documents(match)
    fees = round(sum(float(x.get("fee", 0)) for x in days), 2)
    refunds = await db.invoice_reversals.aggregate([
        {"$match": {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}},
        {"$group": {"_id": None, "amount": {"$sum": "$fee_refund"}}},
    ]).to_list(1)
    if refunds:
        fees = max(0.0, round(fees - float(refunds[0]["amount"]), 2))
    payment = await db.billing_month_payments.find_one({"month": month})
    account = await db.billing_accounts.find_one({"_id": "main"}) or {"balance": 0}
    return {"month": month, "currency": settings["currency"], "invoice_count": count, "fees": fees,
            "days": [{"date": x["_id"], "count": x["count"], "fees": x["fees"], "tax": x["tax"]} for x in days],
            "monthly_paid": bool(payment and payment.get("paid", True)), "balance": round(float(account.get("balance", 0)), 2)}


@router.get("/admin/billing/movements")
async def billing_movements(skip: int = 0, limit: int = 50, user: dict = Depends(require_super_admin)):
    """List the append-only prepaid credit/debit trail for reconciliation."""
    rows = await db.billing_movements.find().sort("created_at", -1).skip(max(0, skip)).to_list(min(max(limit, 1), 100))
    return [{k: v for k, v in row.items() if k != "_id"} for row in rows]


@router.post("/admin/billing/topups")
async def billing_top_up(body: BillingTopUpIn, user: dict = Depends(require_super_admin)):
    """Append a prepaid credit movement and update the single-copy balance."""
    now = now_iso()
    await db.billing_movements.insert_one({"movement_id": secrets.token_urlsafe(18), "kind": "topup", "amount": round(body.amount, 2),
        "note": body.note.strip(), "created_at": now, "created_by": user["id"]})
    await db.billing_accounts.update_one({"_id": "main"}, {"$set": {"updated_at": now, "grace_used": 0}}, upsert=True)
    await refresh_prepaid_balance()
    await audit(user, "billing.topup", f"prepaid top-up {body.amount}: {body.note.strip()}")
    return {"balance": (await db.billing_accounts.find_one({"_id": "main"})).get("balance", 0)}


@router.post("/admin/billing/month-paid")
async def mark_billing_month_paid(body: BillingMonthPaymentIn, user: dict = Depends(require_super_admin)):
    """Set a monthly paid/unpaid status without changing invoice billing ledger rows."""
    await db.billing_month_payments.update_one({"month": body.month}, {"$setOnInsert": {
        "month": body.month}, "$set": {"paid": body.paid, "note": body.note.strip(),
        "updated_at": now_iso(), "updated_by": user["id"]}}, upsert=True)
    await audit(user, "billing.month_status", f"marked {body.month} {'paid' if body.paid else 'unpaid'}")
    return {"month": body.month, "paid": body.paid}
