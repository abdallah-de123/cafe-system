"""Atomic stock changes, movement history, low-stock alerts, and menu availability sync."""
from datetime import datetime, timezone
import uuid

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core.db import clean, db, now_iso, oid
from core.errors import fail
from core.settings import get_settings_doc
from core.ws import manager


def order_inventory_requirements(items: list[dict]) -> list[dict]:
    """Combine menu recipes into one stock requirement per ingredient for this order."""
    totals = {}
    for line in items:
        for ingredient in line.get("inventory_requirements", []):
            item_id = ingredient["inventory_item_id"]
            totals[item_id] = totals.get(item_id, 0.0) + float(ingredient["qty_per_unit"]) * int(line["qty"])
    return [{"inventory_item_id": item_id, "quantity": round(quantity, 6)}
            for item_id, quantity in sorted(totals.items()) if quantity > 0]


async def _effective_threshold(item: dict, settings: dict | None = None) -> float:
    """Use the item's custom alert level, or the restaurant-wide default when not set."""
    settings = settings or await get_settings_doc()
    threshold = item.get("low_stock_threshold")
    return float(settings["default_low_stock_threshold"] if threshold is None else threshold)


async def _refresh_low_stock(item_id: ObjectId):
    """Create one active low-stock alert per crossing and resolve it after restocking."""
    item = await db.inventory_items.find_one({"_id": item_id})
    if not item:
        return
    if not item.get("active", True):
        await db.inventory_items.update_one({"_id": item_id}, {"$set": {"low_stock_alert_active": False}})
        await db.inventory_alerts.update_many(
            {"inventory_item_id": str(item_id), "active": True},
            {"$set": {"active": False, "resolved_at": now_iso()}},
        )
        return
    settings = await get_settings_doc()
    threshold = await _effective_threshold(item, settings)
    quantity = round(float(item.get("quantity", 0)), 6)
    if quantity > threshold:
        await db.inventory_items.update_one({"_id": item_id}, {"$set": {"low_stock_alert_active": False}})
        await db.inventory_alerts.update_many(
            {"inventory_item_id": str(item_id), "active": True},
            {"$set": {"active": False, "resolved_at": now_iso()}},
        )
        return

    await db.inventory_items.update_one({"_id": item_id}, {"$set": {"low_stock_alert_active": True}})
    if not settings.get("alert_in_app", True):
        await db.inventory_alerts.update_many(
            {"inventory_item_id": str(item_id), "active": True},
            {"$set": {"active": False, "resolved_at": now_iso()}},
        )
        return
    existing = await db.inventory_alerts.find_one({"inventory_item_id": str(item_id), "active": True})
    if existing:
        await db.inventory_alerts.update_one({"_id": existing["_id"]}, {"$set": {
            "name": item["name"], "name_en": item.get("name_en", ""), "name_ar": item.get("name_ar", ""),
            "quantity": quantity, "unit": item["unit"], "threshold": threshold,
        }})
        return
    alert = {
        "inventory_item_id": str(item_id), "name": item["name"],
        "name_en": item.get("name_en", ""), "name_ar": item.get("name_ar", ""),
        "quantity": quantity, "unit": item["unit"], "threshold": threshold,
        "active": True, "created_at": now_iso(),
    }
    try:
        result = await db.inventory_alerts.insert_one(alert)
    except DuplicateKeyError:
        return
    alert["_id"] = result.inserted_id
    await manager.broadcast("inventory_alert", clean(alert))


async def refresh_inventory_alerts():
    """Re-evaluate active stock after alert settings change or initial setup."""
    async for item in db.inventory_items.find({"active": True}):
        await _refresh_low_stock(item["_id"])


async def _change_one(item_id: str, delta: float, require_active: bool) -> tuple[dict, dict] | None:
    """Atomically change one quantity, guarding deductions from dropping below zero."""
    item_oid = oid(item_id)
    before = await db.inventory_items.find_one({"_id": item_oid})
    if not before:
        fail(404, "INVENTORY_ITEM_NOT_FOUND", item_id=item_id)
    if require_active and delta < 0 and not before.get("active", True):
        fail(409, "INVENTORY_ITEM_INACTIVE", item=before["name"])
    settings = await get_settings_doc()
    threshold = await _effective_threshold(before, settings)
    query = {"_id": item_oid}
    if require_active and delta < 0:
        query["active"] = True
    if delta < 0:
        query["quantity"] = {"$gte": round(-delta, 6)}
    new_quantity = {"$round": [{"$add": [{"$ifNull": ["$quantity", 0]}, round(delta, 6)]}, 6]}
    after = await db.inventory_items.find_one_and_update(
        query,
        [{"$set": {
            "quantity": new_quantity,
            "updated_at": now_iso(),
            "low_stock_alert_active": {"$lte": [new_quantity, threshold]},
        }}],
        return_document=ReturnDocument.AFTER,
    )
    return (before, after) if after else None


async def _rollback_changes(applied: list[tuple[str, float, dict, dict]]):
    """Compensate earlier atomic changes if a later ingredient cannot be changed."""
    for item_id, delta, _before, _after in reversed(applied):
        await db.inventory_items.update_one(
            {"_id": oid(item_id)},
            {"$inc": {"quantity": round(-delta, 6)}, "$set": {"updated_at": now_iso()}},
        )
    for item_id, _delta, _before, _after in applied:
        await _refresh_low_stock(oid(item_id))
    await sync_menu_availability([item_id for item_id, *_ in applied])


async def apply_inventory_deltas(
    changes: list[dict], user: dict, kind: str, reason: str,
    reference: dict | None = None, require_active: bool = False,
):
    """Apply a group of stock deltas atomically per item, log every movement, and refresh alerts."""
    applied = []
    for change in sorted(changes, key=lambda row: row["inventory_item_id"]):
        item_id = change["inventory_item_id"]
        delta = round(float(change["delta"]), 6)
        if not delta:
            continue
        try:
            result = await _change_one(item_id, delta, require_active)
        except Exception:
            await _rollback_changes(applied)
            raise
        if result is None:
            item = await db.inventory_items.find_one({"_id": oid(item_id)})
            await _rollback_changes(applied)
            if not item:
                fail(404, "INVENTORY_ITEM_NOT_FOUND", item_id=item_id)
            if require_active and delta < 0 and not item.get("active", True):
                fail(409, "INVENTORY_ITEM_INACTIVE", item=item["name"])
            fail(409, "INVENTORY_STOCK_INSUFFICIENT", item=item["name"], available=item.get("quantity", 0))
        before, after = result
        applied.append((item_id, delta, before, after))

    operation_id = uuid.uuid4().hex
    reference = reference or {}
    timestamp = now_iso()
    movements = [{
        "operation_id": operation_id, "inventory_item_id": item_id,
        "name": after["name"], "name_en": after.get("name_en", ""), "name_ar": after.get("name_ar", ""),
        "unit": after["unit"], "kind": kind, "delta": delta,
        "before": round(float(before.get("quantity", 0)), 6),
        "after": round(float(after.get("quantity", 0)), 6), "reason": reason,
        "actor_id": user["id"], "actor_name": user["name"],
        "order_id": reference.get("order_id"), "order_number": reference.get("order_number"),
        "created_at": timestamp,
    } for item_id, delta, before, after in applied]
    try:
        if movements:
            await db.inventory_movements.insert_many(movements, ordered=True)
    except Exception:
        await db.inventory_movements.delete_many({"operation_id": operation_id})
        await _rollback_changes(applied)
        raise

    changed_ids = [item_id for item_id, *_ in applied]
    for item_id in changed_ids:
        await _refresh_low_stock(oid(item_id))
    await sync_menu_availability(changed_ids)
    if changed_ids:
        await manager.broadcast("inventory_updated", {"ids": changed_ids})
    return movements


async def refresh_menu_item_availability(menu_item: dict):
    """Hide only available menu items that have an empty ingredient; restore auto-hidden ones."""
    settings = await get_settings_doc()
    if not settings.get("auto_hide_out_of_stock", True):
        return False
    consumes = menu_item.get("consumes") or []
    ids = []
    for recipe in consumes:
        try:
            ids.append(oid(recipe["inventory_item_id"]))
        except Exception:
            return True
    stock = {}
    if ids:
        async for item in db.inventory_items.find({"_id": {"$in": ids}}):
            stock[str(item["_id"])] = item
    out_of_stock = any(
        str(recipe["inventory_item_id"]) not in stock
        or not stock[str(recipe["inventory_item_id"])].get("active", True)
        or float(stock[str(recipe["inventory_item_id"])].get("quantity", 0)) <= 0
        for recipe in consumes
    )
    if out_of_stock and menu_item.get("available", True):
        await db.menu_items.update_one({"_id": menu_item["_id"]},
                                       {"$set": {"available": False, "inventory_auto_hidden": True}})
        return True
    if not out_of_stock and menu_item.get("inventory_auto_hidden"):
        await db.menu_items.update_one({"_id": menu_item["_id"]},
                                       {"$set": {"available": True}, "$unset": {"inventory_auto_hidden": ""}})
        return True
    return False


async def sync_menu_availability(inventory_item_ids: list[str] | None = None):
    """Re-check menu items linked to changed ingredients and notify customer menus when needed."""
    if not inventory_item_ids:
        query = {"consumes.0": {"$exists": True}}
    else:
        query = {"consumes.inventory_item_id": {"$in": inventory_item_ids}}
    changed = False
    async for menu_item in db.menu_items.find(query):
        changed = await refresh_menu_item_availability(menu_item) or changed
    if changed:
        await manager.broadcast("menu_updated", {})


async def restore_inventory_auto_hidden_items():
    """Restore stock-hidden menu items if the owner turns automatic hiding off."""
    await db.menu_items.update_many(
        {"inventory_auto_hidden": True},
        {"$set": {"available": True}, "$unset": {"inventory_auto_hidden": ""}},
    )
    await manager.broadcast("menu_updated", {})
