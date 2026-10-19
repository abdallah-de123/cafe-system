"""Owner tools for stock levels, adjustments, alerts, and movement history."""
from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import clean, db, now_iso, oid
from core.errors import fail
from core.inventory import apply_inventory_deltas, refresh_inventory_alerts, sync_menu_availability
from core.security import require_manager
from core.settings import get_settings_doc
from core.ws import manager
from models import InventoryItemCreate, InventoryItemUpdate, InventoryMovementIn

router = APIRouter(tags=["inventory"])


def _item_name(item: dict) -> str:
    return item.get("name", "")


@router.get("/inventory")
async def list_inventory(user: dict = Depends(require_manager)):
    """List active and archived stock items for the owner dashboard."""
    docs = await db.inventory_items.find({}).sort("name", 1).to_list(1000)
    settings = await get_settings_doc()
    for item in docs:
        item["effective_low_stock_threshold"] = item.get("low_stock_threshold")
        if item["effective_low_stock_threshold"] is None:
            item["effective_low_stock_threshold"] = settings["default_low_stock_threshold"]
    return [clean(item) for item in docs]


@router.post("/inventory")
async def create_inventory_item(body: InventoryItemCreate, user: dict = Depends(require_manager)):
    """Create a tracked ingredient and record its opening amount as a movement."""
    doc = body.model_dump(exclude={"initial_quantity"})
    doc.update({"quantity": 0.0, "active": True, "low_stock_alert_active": False, "created_at": now_iso()})
    result = await db.inventory_items.insert_one(doc)
    item_id = str(result.inserted_id)
    if body.initial_quantity:
        await apply_inventory_deltas(
            [{"inventory_item_id": item_id, "delta": body.initial_quantity}], user,
            "initial_stock", "Opening stock",
        )
    else:
        await refresh_inventory_alerts()
    await audit(user, "inventory.create", f"created {_item_name(doc)}")
    await manager.broadcast("inventory_updated", {"id": item_id})
    return clean(await db.inventory_items.find_one({"_id": result.inserted_id}))


@router.put("/inventory/{item_id}")
async def update_inventory_item(item_id: str, body: InventoryItemUpdate, user: dict = Depends(require_manager)):
    """Edit item details; all quantity changes stay in the movement endpoint."""
    item_oid = oid(item_id)
    old = await db.inventory_items.find_one({"_id": item_oid})
    if not old:
        fail(404, "INVENTORY_ITEM_NOT_FOUND", item_id=item_id)
    updates = body.model_dump(exclude_unset=True)
    if updates:
        updates["updated_at"] = now_iso()
        await db.inventory_items.update_one({"_id": item_oid}, {"$set": updates})
    if "active" in updates or "low_stock_threshold" in updates:
        await sync_menu_availability([item_id])
        await refresh_inventory_alerts()
    await audit(user, "inventory.update", f"updated {_item_name(old)}")
    await manager.broadcast("inventory_updated", {"id": item_id})
    return clean(await db.inventory_items.find_one({"_id": item_oid}))


@router.post("/inventory/{item_id}/movements")
async def create_movement(item_id: str, body: InventoryMovementIn, user: dict = Depends(require_manager)):
    """Restock, correct, or discard stock and keep a permanent movement record."""
    item = await db.inventory_items.find_one({"_id": oid(item_id)})
    if not item:
        fail(404, "INVENTORY_ITEM_NOT_FOUND", item_id=item_id)
    if not item.get("active", True):
        fail(409, "INVENTORY_ITEM_INACTIVE", item=_item_name(item))
    delta = body.quantity if body.kind in {"restock", "adjustment"} else -body.quantity
    movements = await apply_inventory_deltas(
        [{"inventory_item_id": item_id, "delta": delta}], user, body.kind,
        body.reason.strip(), require_active=True,
    )
    await audit(user, f"inventory.{body.kind}", f"{item['name']}: {delta:+g} {item['unit']} ({body.reason.strip()})")
    await manager.broadcast("inventory_updated", {"id": item_id})
    return clean(movements[0]) if movements else {"ok": True}


@router.get("/inventory/{item_id}/movements")
async def list_movements(item_id: str, limit: int = 100, user: dict = Depends(require_manager)):
    """Show newest stock activity for one ingredient."""
    item_oid = oid(item_id)
    if not await db.inventory_items.find_one({"_id": item_oid}, {"_id": 1}):
        fail(404, "INVENTORY_ITEM_NOT_FOUND", item_id=item_id)
    docs = await db.inventory_movements.find({"inventory_item_id": item_id}).sort("created_at", -1).to_list(max(1, min(limit, 300)))
    return [clean(doc) for doc in docs]


@router.get("/inventory/alerts/active")
async def active_inventory_alerts(user: dict = Depends(require_manager)):
    """List unresolved low-stock alerts for managers."""
    docs = await db.inventory_alerts.find({"active": True}).sort("created_at", -1).to_list(300)
    return [clean(doc) for doc in docs]
