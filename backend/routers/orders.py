"""Orders: creation (server-priced), customer lookup by token, lifecycle, ownership, edits.

Lifecycle: new -> accepted -> preparing -> ready -> delivered -> closed (strictly sequential).
The cashier who accepts an order owns it; only they (or a manager) may change it afterwards.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from pymongo.errors import DuplicateKeyError

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import get_current_user, require_manager, is_manager, rate_limit, user_from_token
from core.settings import get_settings_doc, get_admin_settings
from core.inventory import apply_inventory_deltas, order_inventory_requirements
from core.billing import invoice_amounts, check_prepaid_order_limit, record_invoice_billing, refresh_prepaid_balance
from core.ws import manager
from models import OrderIn, OrderEditIn, StatusIn, MyOrdersIn, CartItemIn, CancelOrderIn, OrderRefundIn

router = APIRouter(tags=["orders"])

STATUS_FLOW = ["new", "accepted", "preparing", "ready", "delivered", "closed"]


async def next_order_number() -> str:
    """Sequential, human-readable order number that doubles as the invoice number."""
    try:
        r = await db.counters.find_one_and_update({"_id": "order"}, {"$inc": {"seq": 1}},
                                                  upsert=True, return_document=True)
    except DuplicateKeyError:
        # Two first requests can race to create the counter; after the winner inserts it,
        # retrying performs a normal atomic increment and returns a distinct sequence.
        r = await db.counters.find_one_and_update({"_id": "order"}, {"$inc": {"seq": 1}},
                                                  return_document=True)
    seq = r["seq"] if r else 1
    return f"INV-{datetime.now(timezone.utc).strftime('%y%m%d')}-{seq:04d}"


async def price_items(items_in: List[CartItemIn]) -> List[dict]:
    """Rebuild every cart line from the database. Client prices/names are ignored (fix S1-S3).

    - unknown menu item -> 400 ITEM_NOT_FOUND
    - sold-out item -> 400 ITEM_UNAVAILABLE
    - unknown option choice -> 400 OPTION_INVALID
    - required option group without a choice -> 400 OPTION_REQUIRED
    """
    out = []
    for line in items_in:
        item = await db.menu_items.find_one({"_id": oid(line.menu_item_id)})
        if not item:
            fail(400, "ITEM_NOT_FOUND", item=line.menu_item_id)
        if not item.get("available", True):
            fail(400, "ITEM_UNAVAILABLE", item=item["name"])
        unit_price = float(item["discount_price"] if item.get("discount_price") is not None else item["price"])
        groups = item.get("options") or []
        chosen = []
        for sel in line.options:
            match = None
            for g in groups:
                if sel.group and g["name"] != sel.group:
                    continue
                for c in g.get("choices", []):
                    if c["label"] == sel.label:
                        match = (g, c)
                        break
                if match:
                    break
            if not match:
                fail(400, "OPTION_INVALID", item=item["name"], option=sel.label)
            g, c = match
            # The customer UI allows one choice per group; reject crafted requests that
            # submit several choices from the same group to inflate a line's price.
            if any(ch["group"] == g["name"] for ch in chosen):
                fail(400, "OPTION_DUPLICATE_GROUP", item=item["name"], group=g["name"])
            chosen.append({"group": g["name"], "label": c["label"], "label_en": c.get("label_en", ""),
                           "label_ar": c.get("label_ar", ""), "price_delta": float(c.get("price_delta", 0))})
        # One choice per required group.
        for g in groups:
            if g.get("required") and not any(ch["group"] == g["name"] for ch in chosen):
                fail(400, "OPTION_REQUIRED", item=item["name"], group=g["name"])
        recipe = [{"inventory_item_id": x["inventory_item_id"], "qty_per_unit": float(x["qty_per_unit"])}
                  for x in (item.get("consumes") or [])]
        out.append({
            "menu_item_id": str(item["_id"]), "name": item["name"],
            "name_en": item.get("name_en", ""), "name_ar": item.get("name_ar", ""),
            "qty": line.qty, "unit_price": unit_price, "options": chosen, "note": line.note.strip(),
            "inventory_requirements": recipe,
        })
    return out


def compute_totals(items: List[dict], settings: dict) -> dict:
    """Subtotal + VAT + service charge from already-priced lines, honoring the on/off switches."""
    subtotal = 0.0
    for it in items:
        line = it["unit_price"] + sum(float(o.get("price_delta", 0)) for o in it.get("options", []))
        subtotal += line * it["qty"]
    tax_rate = settings["tax_rate"] if settings.get("tax_enabled", True) else 0.0
    svc_rate = settings["service_charge"] if settings.get("service_enabled", True) else 0.0
    tax = round(subtotal * tax_rate / 100, 2)
    service = round(subtotal * svc_rate / 100, 2)
    return {"subtotal": round(subtotal, 2), "tax": tax, "service": service,
            "total": round(subtotal + tax + service, 2), "tax_rate": tax_rate, "service_rate": svc_rate}


def customer_view(o: dict) -> dict:
    """What a customer may see of an order (no internal staff ids). Accepts raw or cleaned docs."""
    d = clean(o) if "_id" in o else dict(o)
    for field in ("accepted_by", "cancelled_by", "inventory_consumption"):
        d.pop(field, None)
    for line in d.get("items", []):
        line.pop("inventory_requirements", None)
    return d


# ---------- customer side ----------
@router.post("/orders", dependencies=[Depends(rate_limit("orders", 10))])
async def create_order(body: OrderIn):
    """Customer places an order. Returns the order incl. its secret `public_token`."""
    settings = await get_settings_doc()
    if not settings.get("accepting_orders", True):
        fail(503, "ORDERS_PAUSED")
    admin = await get_admin_settings()
    await check_prepaid_order_limit(admin)
    if not body.items:
        fail(400, "CART_EMPTY")
    if not (1 <= body.table_number <= int(settings["table_count"])):
        fail(400, "TABLE_INVALID")
    if settings.get("require_customer_name") and not body.customer_name.strip():
        fail(400, "CUSTOMER_NAME_REQUIRED")
    items = await price_items(body.items)
    totals = compute_totals(items, settings)
    doc = {
        "order_number": await next_order_number(),
        "public_token": secrets.token_urlsafe(18),
        "table_number": body.table_number,
        "customer_name": body.customer_name.strip(),
        "items": items, **totals,
        "currency": settings["currency"],
        "status": "new", "paid": False,
        "accepted_by": None, "accepted_by_name": None, "modified_by_name": None,
        "history": [{"status": "new", "at": now_iso(), "by": "customer"}],
        "created_at": now_iso(),
    }
    r = await db.orders.insert_one(doc)
    out = clean(await db.orders.find_one({"_id": r.inserted_id}))
    await manager.broadcast("order_created", out)
    return customer_view(out)


@router.post("/orders/mine", dependencies=[Depends(rate_limit("orders_mine", 60))])
async def my_orders(body: MyOrdersIn):
    """Customer fetches the orders whose tokens they hold (tokens are stored on their phone)."""
    if not body.tokens:
        return []
    docs = await db.orders.find({"public_token": {"$in": body.tokens}}).sort("created_at", -1).to_list(50)
    return [customer_view(d) for d in docs]


@router.get("/orders/{order_id}/checkout-summary")
async def checkout_summary(order_id: str, user: dict = Depends(get_current_user)):
    """Return the customer-facing amount the cashier must collect, including any enabled system fee."""
    order = await db.orders.find_one({"_id": oid(order_id)})
    if not order:
        fail(404, "ORDER_NOT_FOUND")
    if not can_modify(order, user):
        fail(403, "ORDER_NOT_OWNER")
    settings = await get_settings_doc()
    admin = await get_admin_settings()
    return {**invoice_amounts(order, settings, admin), "currency": order.get("currency", settings["currency"])}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request, token: str = ""):
    """One order. Staff use their JWT; customers must present the order's token."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        await user_from_token(auth[7:])
        return clean(o)
    if token and secrets.compare_digest(token, o.get("public_token", "")):
        return customer_view(o)
    fail(403, "ORDER_TOKEN_INVALID")


# ---------- staff side ----------
@router.get("/orders")
async def list_orders(scope: str = "all", skip: int = 0, limit: int = 50, user: dict = Depends(get_current_user)):
    """Staff board. Cashiers see new orders plus their own; managers see everything."""
    q: Dict[str, Any] = {}
    if scope == "mine" or not is_manager(user):
        q = {"$or": [{"status": "new"}, {"accepted_by": user["id"]}]}
    docs = await db.orders.find(q).sort("created_at", -1).skip(max(0, skip)).to_list(min(max(limit, 1), 100))
    return [clean(d) for d in docs]


def can_modify(order: dict, user: dict) -> bool:
    """Managers always; cashiers only for orders they accepted."""
    return is_manager(user) or order.get("accepted_by") == user["id"]


@router.post("/orders/{order_id}/accept")
async def accept_order(order_id: str, user: dict = Depends(get_current_user)):
    """Deduct recipe stock once, then assign the order to the accepting cashier."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    settings = await get_settings_doc()
    window = int(settings.get("edit_window_seconds", 60))
    claim = await db.orders.update_one({"_id": oid(order_id), "status": "new"},
                                       {"$set": {"status": "accepting_inventory"}})
    if claim.matched_count == 0:
        fail(400, "ORDER_ALREADY_ACCEPTED")
    requirements = order_inventory_requirements(o.get("items", []))
    try:
        await apply_inventory_deltas(
            [{"inventory_item_id": x["inventory_item_id"], "delta": -x["quantity"]} for x in requirements],
            user, "sale", "Order accepted", {"order_id": order_id, "order_number": o["order_number"]},
            require_active=True,
        )
    except Exception:
        await db.orders.update_one({"_id": oid(order_id), "status": "accepting_inventory"}, {"$set": {"status": "new"}})
        raise
    upd = {"status": "accepted", "accepted_by": user["id"], "accepted_by_name": user["name"],
           "accepted_at": now_iso(), "modified_by_name": user["name"],
           "inventory_consumption": requirements,
           "edit_until": (datetime.now(timezone.utc) + timedelta(seconds=window)).isoformat()}
    res = await db.orders.update_one({"_id": oid(order_id), "status": "accepting_inventory"}, {
        "$set": upd, "$push": {"history": {"status": "accepted", "at": now_iso(), "by": user["name"]}}})
    if res.matched_count == 0:
        fail(400, "ORDER_ALREADY_ACCEPTED")
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.accept", f"accepted {o['order_number']}")
    await manager.broadcast("order_updated", out)
    return out


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, body: CancelOrderIn, user: dict = Depends(get_current_user)):
    """Cancel an unfinished order and return its consumed stock exactly once."""
    order_oid = oid(order_id)
    order = await db.orders.find_one({"_id": order_oid})
    if not order:
        fail(404, "ORDER_NOT_FOUND")
    if order["status"] not in {"new", "accepted", "preparing", "ready"}:
        fail(400, "ORDER_CANNOT_CANCEL")
    if order["status"] != "new" and not can_modify(order, user):
        fail(403, "ORDER_NOT_OWNER")
    old_status = order["status"]
    claim = await db.orders.update_one(
        {"_id": order_oid, "status": old_status}, {"$set": {"status": "cancelling_inventory"}}
    )
    if claim.matched_count == 0:
        fail(409, "ORDER_ALREADY_CHANGED")
    try:
        consumed = order.get("inventory_consumption", []) if old_status != "new" else []
        await apply_inventory_deltas(
            [{"inventory_item_id": x["inventory_item_id"], "delta": x["quantity"]} for x in consumed],
            user, "cancel_return", body.reason.strip(),
            {"order_id": order_id, "order_number": order["order_number"]},
        )
    except Exception:
        await db.orders.update_one({"_id": order_oid, "status": "cancelling_inventory"}, {"$set": {"status": old_status}})
        raise
    now = now_iso()
    await db.orders.update_one({"_id": order_oid, "status": "cancelling_inventory"}, {
        "$set": {"status": "cancelled", "cancelled_at": now, "cancelled_by": user["id"],
                 "cancelled_by_name": user["name"], "cancel_reason": body.reason.strip(),
                 "modified_by_name": user["name"]},
        "$push": {"history": {"status": "cancelled", "at": now, "by": user["name"],
                                "reason": body.reason.strip()}}})
    out = clean(await db.orders.find_one({"_id": order_oid}))
    await audit(user, "order.cancel", f"cancelled {order['order_number']}: {body.reason.strip()}")
    await manager.broadcast("order_updated", out)
    return out


@router.post("/orders/{order_id}/status")
async def set_status(order_id: str, body: StatusIn, user: dict = Depends(get_current_user)):
    """Move an order one step forward. Closing marks it paid and makes it immutable."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    if not can_modify(o, user):
        fail(403, "ORDER_NOT_OWNER")
    cur, nxt = o["status"], body.status
    if cur not in STATUS_FLOW:
        fail(400, "STATUS_INVALID")
    if nxt not in STATUS_FLOW:
        fail(400, "STATUS_INVALID")
    if STATUS_FLOW.index(nxt) != STATUS_FLOW.index(cur) + 1:
        fail(400, "STATUS_NOT_SEQUENTIAL", current=cur)
    upd = {"status": nxt, "modified_by_name": user["name"], f"{nxt}_at": now_iso()}
    if nxt == "closed":
        if body.payment_method is None or body.amount_received is None:
            fail(422, "PAYMENT_DETAILS_REQUIRED")
        settings = await get_settings_doc()
        if not settings.get("payment_methods", {}).get(body.payment_method, False):
            fail(400, "PAYMENT_METHOD_DISABLED")
        settings = await get_settings_doc()
        admin = await get_admin_settings()
        amounts = invoice_amounts(o, settings, admin)
        if float(body.amount_received) < amounts["invoice_total"]:
            fail(400, "PAYMENT_AMOUNT_INSUFFICIENT")
        closed_at = now_iso()
        upd["paid"] = True
        upd.update({**amounts, "payment_method": body.payment_method, "amount_received": round(float(body.amount_received), 2),
                    "change_given": round(float(body.amount_received) - amounts["invoice_total"], 2),
                    "billing_enabled_at_close": bool(admin.get("billing_enabled")), "billing_mode": admin.get("billing_mode"),
                    "closed_by": user["id"], "closed_by_name": user["name"], "closed_at": closed_at})
    res = await db.orders.update_one({"_id": oid(order_id), "status": cur}, {
        "$set": upd, "$push": {"history": {"status": nxt, "at": now_iso(), "by": user["name"]}}})
    if not res.matched_count:
        fail(409, "ORDER_ALREADY_CHANGED")
    if nxt == "closed":
        updated_order = await db.orders.find_one({"_id": oid(order_id)})
        await record_invoice_billing(updated_order, amounts, admin)
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.status", f"{o['order_number']}: {cur} -> {nxt}")
    await manager.broadcast("order_updated", out)
    return out


@router.post("/orders/{order_id}/refund")
async def refund_order(order_id: str, body: OrderRefundIn, user: dict = Depends(require_manager)):
    """Record a partial/full refund as an append-only reversal; never edits the original billing ledger row."""
    order_oid = oid(order_id)
    order = await db.orders.find_one({"_id": order_oid})
    if not order:
        fail(404, "ORDER_NOT_FOUND")
    if not order.get("paid"):
        fail(400, "ORDER_NOT_PAID")
    invoice_total = float(order.get("invoice_total", order.get("total", 0)))
    refunded = float(order.get("refunded_total", 0))
    amount = round(float(body.amount if body.amount is not None else invoice_total - refunded), 2)
    if amount <= 0 or amount > round(invoice_total - refunded, 2):
        fail(400, "REFUND_AMOUNT_INVALID")
    new_refunded = round(refunded + amount, 2)
    # Compare-and-set prevents concurrent partial refunds from exceeding the invoice total.
    res = await db.orders.update_one({"_id": order_oid, "paid": True, "refunded_total": refunded},
                                     {"$set": {"refunded_total": new_refunded}})
    if not res.matched_count and refunded == 0:
        res = await db.orders.update_one({"_id": order_oid, "paid": True, "refunded_total": {"$exists": False}},
                                         {"$set": {"refunded_total": new_refunded}})
    if not res.matched_count:
        fail(409, "ORDER_ALREADY_CHANGED")
    admin = await get_admin_settings()
    fee_refund = 0.0
    if admin.get("reversal_refunds_fee") and invoice_total:
        prior_refunds = await db.invoice_reversals.aggregate([
            {"$match": {"order_id": order_id}}, {"$group": {"_id": None, "fee_refund": {"$sum": "$fee_refund"}}},
        ]).to_list(1)
        remaining_fee = max(0.0, float(order.get("system_fee", 0)) - (float(prior_refunds[0]["fee_refund"]) if prior_refunds else 0))
        fee_refund = min(remaining_fee, round(amount * float(order.get("system_fee", 0)) / invoice_total, 2))
    reversal_id = secrets.token_urlsafe(18)
    reversal = {"reversal_id": reversal_id, "order_id": order_id, "order_number": order.get("order_number"),
                "amount": amount, "fee_refund": fee_refund, "currency": order.get("currency"),
                "reason": body.reason, "created_at": now_iso(), "created_by": user["id"], "created_by_name": user["name"]}
    await db.invoice_reversals.insert_one(reversal)
    if fee_refund and order.get("billing_mode") == "prepaid":
        await db.billing_movements.insert_one({"movement_id": f"refund:{reversal_id}", "reversal_id": reversal_id, "kind": "refund", "amount": fee_refund,
                                               "order_id": order_id, "created_at": reversal["created_at"]})
        await refresh_prepaid_balance()
    await audit(user, "order.refund", f"{order['order_number']}: {amount} ({body.reason})")
    return {k: v for k, v in reversal.items() if k != "_id"}


@router.put("/orders/{order_id}/items")
async def edit_order(order_id: str, body: OrderEditIn, user: dict = Depends(get_current_user)):
    """Change items of an accepted order inside the edit window (managers are exempt from the window)."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    if o["status"] in {"closed", "cancelled"}:
        fail(400, "ORDER_CLOSED")
    if not can_modify(o, user):
        fail(403, "ORDER_NOT_OWNER")
    if not is_manager(user):
        limit = o.get("edit_until")
        if not limit or datetime.fromisoformat(limit) < datetime.now(timezone.utc):
            fail(400, "EDIT_WINDOW_CLOSED")
    if not body.items:
        fail(400, "CART_EMPTY")
    settings = await get_settings_doc()
    items = await price_items(body.items)
    totals = compute_totals(items, settings)
    order_oid = oid(order_id)
    old_status = o["status"]
    claim = await db.orders.update_one({"_id": order_oid, "status": old_status},
                                       {"$set": {"status": "editing_inventory"}})
    if claim.matched_count == 0:
        fail(409, "ORDER_ALREADY_CHANGED")
    old_requirements = o.get("inventory_consumption", []) if old_status not in {"new", "accepting_inventory"} else []
    new_requirements = order_inventory_requirements(items) if old_requirements or old_status not in {"new", "accepting_inventory"} else []
    old_by_id = {x["inventory_item_id"]: float(x["quantity"]) for x in old_requirements}
    new_by_id = {x["inventory_item_id"]: float(x["quantity"]) for x in new_requirements}
    changes = [{"inventory_item_id": item_id, "delta": round(new_by_id.get(item_id, 0) - old_by_id.get(item_id, 0), 6)}
               for item_id in sorted(set(old_by_id) | set(new_by_id))]
    try:
        await apply_inventory_deltas(
            changes, user, "order_edit", "Order items edited",
            {"order_id": order_id, "order_number": o["order_number"]}, require_active=True,
        )
    except Exception:
        await db.orders.update_one({"_id": order_oid, "status": "editing_inventory"}, {"$set": {"status": old_status}})
        raise
    await db.orders.update_one({"_id": order_oid, "status": "editing_inventory"}, {
        "$set": {"status": old_status, "items": items, **totals,
                 "inventory_consumption": new_requirements if old_status != "new" else [],
                 "modified_by_name": user["name"]},
        "$push": {"history": {"status": "edited", "at": now_iso(), "by": user["name"],
                              "detail": f"{len(items)} lines, total {totals['total']}"}}})
    out = clean(await db.orders.find_one({"_id": order_oid}))
    await audit(user, "order.edit", f"edited items of {o['order_number']}")
    await manager.broadcast("order_updated", out)
    return out
