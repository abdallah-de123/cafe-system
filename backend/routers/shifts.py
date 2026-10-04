"""Shifts (start/end with cash summary), reports, and the audit log view."""
from datetime import datetime, timezone, timedelta
from typing import Dict

from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db, clean, now_iso
from core.errors import fail
from core.security import get_current_user, require_manager, is_manager

router = APIRouter(tags=["shifts", "reports"])


@router.get("/shifts/current")
async def current_shift(user: dict = Depends(get_current_user)):
    """The caller's open shift, or null."""
    return clean(await db.shifts.find_one({"user_id": user["id"], "status": "open"}))


@router.post("/shifts/start")
async def start_shift(user: dict = Depends(get_current_user)):
    """Open a shift (idempotent: returns the existing open one)."""
    ex = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if ex:
        return clean(ex)
    doc = {"user_id": user["id"], "user_name": user["name"], "status": "open", "started_at": now_iso()}
    r = await db.shifts.insert_one(doc)
    await audit(user, "shift.start", f"{user['name']} started shift")
    return clean(await db.shifts.find_one({"_id": r.inserted_id}))


@router.post("/shifts/end")
async def end_shift(user: dict = Depends(get_current_user)):
    """Close the shift and summarize the orders this cashier accepted during it."""
    s = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if not s:
        fail(400, "NO_ACTIVE_SHIFT")
    orders = await db.orders.find({"accepted_by": user["id"],
                                   "accepted_at": {"$gte": s["started_at"]}}).to_list(1000)
    total_cash = sum(o["total"] for o in orders if o.get("paid"))
    await db.shifts.update_one({"_id": s["_id"]}, {"$set": {
        "status": "closed", "ended_at": now_iso(),
        "orders_count": len(orders), "total_cash": round(total_cash, 2)}})
    await audit(user, "shift.end", f"{user['name']} ended shift, {len(orders)} orders")
    return clean(await db.shifts.find_one({"_id": s["_id"]}))


@router.get("/shifts")
async def list_shifts(user: dict = Depends(get_current_user)):
    """Managers see all shifts; cashiers only their own."""
    q = {} if is_manager(user) else {"user_id": user["id"]}
    docs = await db.shifts.find(q).sort("started_at", -1).to_list(100)
    return [clean(d) for d in docs]


@router.get("/reports")
async def reports(period: str = "day", user: dict = Depends(require_manager)):
    """Simple rolling-window report (calendar/timezone-aware version comes in Phase 4)."""
    days = {"day": 1, "week": 7, "month": 30}.get(period, 1)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    orders = await db.orders.find({"created_at": {"$gte": since}}).to_list(2000)
    paid = [o for o in orders if o.get("paid")]
    revenue = sum(o["total"] for o in paid)
    item_counts: Dict[str, int] = {}
    hours: Dict[str, int] = {}
    for o in orders:
        for it in o["items"]:
            item_counts[it["name"]] = item_counts.get(it["name"], 0) + it["qty"]
        h = datetime.fromisoformat(o["created_at"]).strftime("%H:00")
        hours[h] = hours.get(h, 0) + 1
    ranked = sorted(item_counts.items(), key=lambda x: -x[1])
    return {
        "period": period, "orders_count": len(orders), "paid_count": len(paid),
        "revenue": round(revenue, 2),
        "avg_order_value": round(revenue / len(paid), 2) if paid else 0,
        "best_sellers": [{"name": n, "qty": q} for n, q in ranked[:5]],
        "worst_sellers": [{"name": n, "qty": q} for n, q in ranked[-5:][::-1]],
        "busiest_hours": [{"hour": h, "orders": c} for h, c in sorted(hours.items())],
    }


@router.get("/audit")
async def audit_list(user: dict = Depends(require_manager)):
    """Latest audit entries for managers."""
    docs = await db.audit_logs.find().sort("created_at", -1).to_list(200)
    return [clean(d) for d in docs]
