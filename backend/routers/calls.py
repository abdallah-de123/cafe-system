"""Waiter calls (help / bill / clean) and customer ratings."""
from fastapi import APIRouter, Depends

from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import get_current_user, rate_limit
from core.settings import get_settings_doc
from core.ws import manager
from models import CallIn, RatingIn

router = APIRouter(tags=["calls", "ratings"])


@router.post("/calls", dependencies=[Depends(rate_limit("calls", 6))])
async def create_call(body: CallIn):
    """Customer presses a quick-action button. Table must exist."""
    settings = await get_settings_doc()
    if not (1 <= body.table_number <= int(settings["table_count"])):
        fail(400, "TABLE_INVALID")
    doc = {"table_number": body.table_number, "kind": body.kind, "status": "open",
           "created_at": now_iso(), "handled_by_name": None}
    r = await db.calls.insert_one(doc)
    out = clean(await db.calls.find_one({"_id": r.inserted_id}))
    await manager.broadcast("call_created", out)
    return out


@router.get("/calls")
async def list_calls(user: dict = Depends(get_current_user)):
    """Staff list of recent calls."""
    docs = await db.calls.find().sort("created_at", -1).to_list(100)
    return [clean(d) for d in docs]


@router.post("/calls/{cid}/resolve")
async def resolve_call(cid: str, user: dict = Depends(get_current_user)):
    """Staff marks a call handled."""
    res = await db.calls.update_one({"_id": oid(cid)}, {"$set": {
        "status": "resolved", "handled_by_name": user["name"], "resolved_at": now_iso()}})
    if res.matched_count == 0:
        fail(404, "CALL_NOT_FOUND")
    out = clean(await db.calls.find_one({"_id": oid(cid)}))
    await manager.broadcast("call_updated", out)
    return out


@router.post("/ratings", dependencies=[Depends(rate_limit("ratings", 6))])
async def create_rating(body: RatingIn):
    """Customer rates a delivered/closed order once. They must hold the order token."""
    o = await db.orders.find_one({"_id": oid(body.order_id)})
    if not o:
        fail(404, "ORDER_NOT_FOUND")
    if not body.token or body.token != o.get("public_token"):
        fail(403, "ORDER_TOKEN_INVALID")
    if o["status"] not in ("delivered", "closed"):
        fail(400, "RATING_TOO_EARLY")
    if await db.ratings.find_one({"order_id": body.order_id}):
        fail(400, "RATING_EXISTS")
    doc = body.model_dump(exclude={"token"})
    doc["created_at"] = now_iso()
    await db.ratings.insert_one(doc)
    return {"ok": True}


@router.get("/ratings")
async def list_ratings(user: dict = Depends(get_current_user)):
    """Staff view of ratings (managers only)."""
    if user["role"] == "cashier":
        fail(403, "FORBIDDEN")
    docs = await db.ratings.find().sort("created_at", -1).to_list(200)
    return [clean(d) for d in docs]
