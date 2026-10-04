"""Orders: creation (server-priced), customer lookup by token, lifecycle, ownership, edits.

Lifecycle: new -> accepted -> preparing -> ready -> delivered -> closed (strictly sequential).
The cashier who accepts an order owns it; only they (or a manager) may change it afterwards.
"""
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import get_current_user, is_manager, rate_limit, user_from_token
from core.settings import get_settings_doc
from core.ws import manager
from models import OrderIn, OrderEditIn, StatusIn, MyOrdersIn, CartItemIn

router = APIRouter(tags=["orders"])

STATUS_FLOW = ["new", "accepted", "preparing", "ready", "delivered", "closed"]


async def next_order_number() -> str:
    """Sequential, human-readable order number that doubles as the invoice number."""
    r = await db.counters.find_one_and_update({"_id": "order"}, {"$inc": {"seq": 1}},
                                              upsert=True, return_document=True)
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
            chosen.append({"group": g["name"], "label": c["label"], "label_en": c.get("label_en", ""),
                           "label_ar": c.get("label_ar", ""), "price_delta": float(c.get("price_delta", 0))})
        # One choice per required group.
        for g in groups:
            if g.get("required") and not any(ch["group"] == g["name"] for ch in chosen):
                fail(400, "OPTION_REQUIRED", item=item["name"], group=g["name"])
        out.append({
            "menu_item_id": str(item["_id"]), "name": item["name"],
            "name_en": item.get("name_en", ""), "name_ar": item.get("name_ar", ""),
            "qty": line.qty, "unit_price": unit_price, "options": chosen, "note": line.note.strip(),
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
    """What a customer may see of an order (no internal staff ids)."""
    d = clean(o)
    d.pop("accepted_by", None)
    return d


# ---------- customer side ----------
@router.post("/orders", dependencies=[Depends(rate_limit("orders", 10))])
async def create_order(body: OrderIn):
    """Customer places an order. Returns the order incl. its secret `public_token`."""
    settings = await get_settings_doc()
    if not settings.get("accepting_orders", True):
        fail(503, "ORDERS_PAUSED")
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
async def list_orders(scope: str = "all", user: dict = Depends(get_current_user)):
    """Staff board. Cashiers see new orders plus their own; managers see everything."""
    q: Dict[str, Any] = {}
    if scope == "mine" or not is_manager(user):
        q = {"$or": [{"status": "new"}, {"accepted_by": user["id"]}]}
    docs = await db.orders.find(q).sort("created_at", -1).to_list(300)
    return [clean(d) for d in docs]


def can_modify(order: dict, user: dict) -> bool:
    """Managers always; cashiers only for orders they accepted."""
    return is_manager(user) or order.get("accepted_by") == user["id"]


@router.post("/orders/{order_id}/accept")
async def accept_order(order_id: str, user: dict = Depends(get_current_user)):
    """Cashier takes ownership of a new order and opens the edit window."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    settings = await get_settings_doc()
    window = int(settings.get("edit_window_seconds", 60))
    upd = {"status": "accepted", "accepted_by": user["id"], "accepted_by_name": user["name"],
           "accepted_at": now_iso(), "modified_by_name": user["name"],
           "edit_until": (datetime.now(timezone.utc) + timedelta(seconds=window)).isoformat()}
    # Atomic: only succeeds if the order is still "new", so two cashiers cannot both accept it.
    res = await db.orders.update_one({"_id": oid(order_id), "status": "new"}, {
        "$set": upd, "$push": {"history": {"status": "accepted", "at": now_iso(), "by": user["name"]}}})
    if res.matched_count == 0:
        fail(400, "ORDER_ALREADY_ACCEPTED")
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.accept", f"accepted {o['order_number']}")
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
    if nxt not in STATUS_FLOW:
        fail(400, "STATUS_INVALID")
    if STATUS_FLOW.index(nxt) != STATUS_FLOW.index(cur) + 1:
        fail(400, "STATUS_NOT_SEQUENTIAL", current=cur)
    upd = {"status": nxt, "modified_by_name": user["name"], f"{nxt}_at": now_iso()}
    if nxt == "closed":
        upd["paid"] = True
    await db.orders.update_one({"_id": oid(order_id)}, {
        "$set": upd, "$push": {"history": {"status": nxt, "at": now_iso(), "by": user["name"]}}})
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.status", f"{o['order_number']}: {cur} -> {nxt}")
    await manager.broadcast("order_updated", out)
    return out


@router.put("/orders/{order_id}/items")
async def edit_order(order_id: str, body: OrderEditIn, user: dict = Depends(get_current_user)):
    """Change items of an accepted order inside the edit window (managers are exempt from the window)."""
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    if o["status"] == "closed":
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
    await db.orders.update_one({"_id": oid(order_id)}, {
        "$set": {"items": items, **totals, "modified_by_name": user["name"]},
        "$push": {"history": {"status": "edited", "at": now_iso(), "by": user["name"],
                              "detail": f"{len(items)} lines, total {totals['total']}"}}})
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.edit", f"edited items of {o['order_number']}")
    await manager.broadcast("order_updated", out)
    return out
