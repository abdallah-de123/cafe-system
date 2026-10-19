"""Copy-local invoice billing helpers. Ledger rows are append-only and keyed by order."""
from core.db import db, now_iso


def invoice_amounts(order: dict, settings: dict, admin: dict) -> dict:
    """Split restaurant revenue from the system fee and apply restaurant tax to the fee."""
    restaurant_total = round(float(order.get("total", 0)), 2)
    fee = round(float(admin.get("fee_per_invoice", 1000)), 2) if admin.get("billing_enabled") else 0.0
    fee_tax = round(fee * float(settings.get("tax_rate", 0)) / 100, 2) if fee and settings.get("tax_enabled", True) else 0.0
    return {"restaurant_total": restaurant_total, "system_fee": fee, "system_fee_tax": fee_tax,
            "invoice_total": round(restaurant_total + fee + fee_tax, 2)}


async def check_prepaid_order_limit(admin: dict):
    """Apply the configured zero-balance policy before creating a new order."""
    if not admin.get("billing_enabled") or admin.get("billing_mode") != "prepaid":
        return
    account = await db.billing_accounts.find_one({"_id": "main"}) or {"balance": 0, "grace_used": 0}
    if float(account.get("balance", 0)) > 0:
        return
    behavior = admin.get("zero_balance_behavior", "warn_grace")
    if behavior == "block":
        from core.errors import fail
        fail(402, "BILLING_BALANCE_EMPTY")
    if behavior == "warn_grace":
        used = int(account.get("grace_used", 0))
        if used >= int(admin.get("grace_invoices", 20)):
            from core.errors import fail
            fail(402, "BILLING_GRACE_EXHAUSTED")
        await db.billing_accounts.update_one({"_id": "main"}, {"$inc": {"grace_used": 1}}, upsert=True)


async def record_invoice_billing(order: dict, amounts: dict, admin: dict, refresh_balance: bool = True):
    """Insert one permanent billing record per paid invoice; debit prepaid fee once."""
    if not admin.get("billing_enabled") or amounts["system_fee"] <= 0:
        return
    order_id = order["id"] if "id" in order else str(order["_id"])
    now = now_iso()
    row = {"order_id": order_id, "order_number": order.get("order_number"),
           "fee": amounts["system_fee"], "fee_tax": amounts["system_fee_tax"],
           "currency": order.get("currency"), "mode": admin.get("billing_mode", "monthly"),
           "closed_at": order.get("closed_at", now), "created_at": now}
    try:
        await db.billing_ledger.insert_one(row)
    except Exception as exc:
        # A retry after an ambiguous network result is safe because the order id is unique.
        from pymongo.errors import DuplicateKeyError
        if isinstance(exc, DuplicateKeyError):
            row = await db.billing_ledger.find_one({"order_id": order_id})
            if not row:
                raise
        else:
            raise
    if row["mode"] == "prepaid":
        # Ledger row is the idempotency key; store the debit as an append-only movement.
        await db.billing_movements.update_one({"movement_id": f"invoice:{order_id}"},
            {"$setOnInsert": {"movement_id": f"invoice:{order_id}", "order_id": order_id,
                              "kind": "invoice", "amount": -row["fee"], "created_at": now}}, upsert=True)
        if refresh_balance:
            await refresh_prepaid_balance()


async def refresh_prepaid_balance():
    """Derive the cached balance from immutable movements so retries cannot double-debit."""
    rows = await db.billing_movements.aggregate([{"$group": {"_id": None, "balance": {"$sum": "$amount"}}}]).to_list(1)
    balance = round(float(rows[0]["balance"]), 2) if rows else 0.0
    await db.billing_accounts.update_one({"_id": "main"}, {"$set": {"balance": balance}}, upsert=True)


async def reconcile_prepaid_ledger():
    """Repair invoice ledger/movement writes interrupted by a process exit."""
    paid_orders = await db.orders.find({"paid": True, "billing_enabled_at_close": True,
                                        "system_fee": {"$gt": 0}}).to_list(100000)
    for order in paid_orders:
        order_id = str(order["_id"])
        if not await db.billing_ledger.find_one({"order_id": order_id}):
            amounts = {key: float(order.get(key, 0)) for key in ("restaurant_total", "system_fee", "system_fee_tax", "invoice_total")}
            await record_invoice_billing(order, amounts,
                {"billing_enabled": True, "billing_mode": order.get("billing_mode", "monthly")}, refresh_balance=False)
    ledger = await db.billing_ledger.find({"mode": "prepaid"}).to_list(100000)
    for row in ledger:
        order_id = row["order_id"]
        await db.billing_movements.update_one({"movement_id": f"invoice:{order_id}"},
            {"$setOnInsert": {"movement_id": f"invoice:{order_id}", "order_id": order_id,
                              "kind": "invoice", "amount": -float(row["fee"]), "created_at": row.get("created_at", now_iso())}}, upsert=True)
    await refresh_prepaid_balance()
