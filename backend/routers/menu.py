"""Menu routes: public listing, owner CRUD, cashier availability toggle, categories."""
from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import require_manager, get_current_user
from core.ws import manager
from core.uploads import cleanup_image_if_unused, thumbnail_url
from core.inventory import refresh_menu_item_availability
from models import MenuItemIn, AvailabilityIn
from seed import CATEGORY_I18N

router = APIRouter(tags=["menu"])


async def validated_menu_doc(body: MenuItemIn) -> dict:
    """Ensure a recipe points only to active stock items and merge duplicate ingredients."""
    doc = body.model_dump()
    consumes = {}
    for recipe in doc.get("consumes", []):
        item_id = recipe["inventory_item_id"]
        stock = await db.inventory_items.find_one({"_id": oid(item_id), "active": True})
        if not stock:
            fail(422, "INVENTORY_ITEM_NOT_ACTIVE", item=item_id)
        consumes[item_id] = consumes.get(item_id, 0.0) + float(recipe["qty_per_unit"])
    doc["consumes"] = [{"inventory_item_id": key, "qty_per_unit": round(value, 6)}
                       for key, value in sorted(consumes.items())]
    return doc


@router.get("/menu")
async def list_menu(include_unavailable: bool = True):
    """Public menu. Customers still see sold-out items (greyed out) so the layout is stable."""
    q = {} if include_unavailable else {"available": True}
    docs = await db.menu_items.find(q).sort("name", 1).to_list(500)
    public = []
    for doc in docs:
        doc.pop("consumes", None)
        doc.pop("inventory_auto_hidden", None)
        public.append(clean(doc))
    return public


@router.get("/menu/manage")
async def manage_menu(user: dict = Depends(require_manager)):
    """Manager-only menu view includes recipe details for editing."""
    docs = await db.menu_items.find({}).sort("name", 1).to_list(500)
    return [clean(doc) for doc in docs]


@router.post("/menu")
async def create_menu(body: MenuItemIn, user: dict = Depends(require_manager)):
    """Owner/super admin adds a menu item."""
    doc = await validated_menu_doc(body)
    # Use only the thumbnail paired with the full image URL uploaded by this app.
    doc["image_thumbnail"] = thumbnail_url(body.image)
    doc["created_at"] = now_iso()
    r = await db.menu_items.insert_one(doc)
    await refresh_menu_item_availability(await db.menu_items.find_one({"_id": r.inserted_id}))
    await audit(user, "menu.create", f"created item {body.name}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": r.inserted_id}))


@router.put("/menu/{mid}")
async def update_menu(mid: str, body: MenuItemIn, user: dict = Depends(require_manager)):
    """Owner/super admin edits a menu item. Price changes get their own audit action."""
    old = await db.menu_items.find_one({"_id": oid(mid)})
    if not old:
        fail(404, "ITEM_NOT_FOUND")
    doc = await validated_menu_doc(body)
    # Keep the preview tied to the saved image, including for legacy external image URLs.
    doc["image_thumbnail"] = thumbnail_url(body.image)
    await db.menu_items.update_one({"_id": oid(mid)}, {"$set": doc})
    await refresh_menu_item_availability(await db.menu_items.find_one({"_id": oid(mid)}))
    if old.get("image") and old.get("image") != body.image:
        await cleanup_image_if_unused(old["image"])
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
    await db.menu_items.update_one({"_id": oid(mid)}, {"$set": {"available": body.available}, "$unset": {"inventory_auto_hidden": ""}})
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
    await cleanup_image_if_unused(doc.get("image", ""))
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
