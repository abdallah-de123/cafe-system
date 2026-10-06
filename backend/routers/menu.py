"""Menu routes: public listing, owner CRUD, cashier availability toggle, categories."""
from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import require_manager, get_current_user
from core.ws import manager
from models import MenuItemIn, AvailabilityIn
from seed import CATEGORY_I18N

router = APIRouter(tags=["menu"])


@router.get("/menu")
async def list_menu(include_unavailable: bool = True):
    """Public menu. Customers still see sold-out items (greyed out) so the layout is stable."""
    q = {} if include_unavailable else {"available": True}
    docs = await db.menu_items.find(q).sort("name", 1).to_list(500)
    return [clean(d) for d in docs]


@router.post("/menu")
async def create_menu(body: MenuItemIn, user: dict = Depends(require_manager)):
    """Owner/super admin adds a menu item."""
    doc = body.model_dump()
    doc["created_at"] = now_iso()
    r = await db.menu_items.insert_one(doc)
    await audit(user, "menu.create", f"created item {body.name}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": r.inserted_id}))


@router.put("/menu/{mid}")
async def update_menu(mid: str, body: MenuItemIn, user: dict = Depends(require_manager)):
    """Owner/super admin edits a menu item. Price changes get their own audit action."""
    old = await db.menu_items.find_one({"_id": oid(mid)})
    if not old:
        fail(404, "ITEM_NOT_FOUND")
    await db.menu_items.update_one({"_id": oid(mid)}, {"$set": body.model_dump()})
    if float(old.get("price", 0)) != float(body.price):
        await audit(user, "menu.price_change", f"{body.name}: {old.get('price')} -> {body.price}")
    else:
        await audit(user, "menu.update", f"updated item {body.name}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": oid(mid)}))


@router.patch("/menu/{mid}/availability")
async def set_availability(mid: str, body: AvailabilityIn, user: dict = Depends(get_current_user)):
    """Any staff member (incl. cashier) marks an item sold out / available again."""
    doc = await db.menu_items.find_one({"_id": oid(mid)})
    if not doc:
        fail(404, "ITEM_NOT_FOUND")
    await db.menu_items.update_one({"_id": oid(mid)}, {"$set": {"available": body.available}})
    await audit(user, "menu.availability", f"{doc.get('name')}: {'available' if body.available else 'sold out'}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": oid(mid)}))


@router.delete("/menu/{mid}")
async def delete_menu(mid: str, user: dict = Depends(require_manager)):
    """Owner/super admin removes a menu item."""
    doc = await db.menu_items.find_one({"_id": oid(mid)})
    if not doc:
        fail(404, "ITEM_NOT_FOUND")
    await db.menu_items.delete_one({"_id": oid(mid)})
    await audit(user, "menu.delete", f"deleted item {doc.get('name')}")
    await manager.broadcast("menu_updated", {})
    return {"ok": True}


@router.get("/categories")
async def categories():
    """Categories derived from menu items with built-in translations (real collection comes in Phase 5)."""
    docs = await db.menu_items.find({}, {"category": 1}).to_list(500)
    names = sorted({d["category"] for d in docs})
    return [{"name": n, "name_en": CATEGORY_I18N.get(n, {}).get("en", n),
             "name_ar": CATEGORY_I18N.get(n, {}).get("ar", n)} for n in names]
