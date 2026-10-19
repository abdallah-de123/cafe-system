"""Cashier shifts, timezone-aware growth reports, and the audit log view."""

from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db, clean, now_iso
from core.errors import fail
from core.security import get_current_user, require_manager, is_manager
from core.settings import get_settings_doc
from core.reporting import business_range
from models import ShiftStartIn, ShiftEndIn

router = APIRouter(tags=["shifts", "reports"])


@router.get("/shifts/current")
async def current_shift(user: dict = Depends(get_current_user)):
    """The caller's open shift, or null."""
    return clean(await db.shifts.find_one({"user_id": user["id"], "status": "open"}))


@router.post("/shifts/start")
async def start_shift(body: ShiftStartIn | None = None, user: dict = Depends(get_current_user)):
    """Open a shift (idempotent: returns the existing open one)."""
    ex = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if ex:
        return clean(ex)
    doc = {"user_id": user["id"], "user_name": user["name"], "status": "open",
           "opening_cash": float(body.opening_cash) if body else 0.0, "started_at": now_iso()}
    r = await db.shifts.insert_one(doc)
    await audit(user, "shift.start", f"{user['name']} started shift")
    return clean(await db.shifts.find_one({"_id": r.inserted_id}))


@router.post("/shifts/end")
async def end_shift(body: ShiftEndIn, user: dict = Depends(get_current_user)):
    """Close the shift and compare counted cash with the cash expected in the drawer."""
    s = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if not s:
        fail(400, "NO_ACTIVE_SHIFT")
    sales_rows = await db.orders.aggregate([
        {"$match": {"closed_by": user["id"], "closed_at": {"$gte": s["started_at"]}, "paid": True}},
        {"$group": {"_id": None, "orders_count": {"$sum": 1},
                    "cash_sales": {"$sum": {"$cond": [{"$eq": ["$payment_method", "cash"]}, {"$ifNull": ["$invoice_total", "$total"]}, 0]}},
                    "total_sales": {"$sum": {"$ifNull": ["$invoice_total", "$total"]}}}},
    ]).to_list(1)
    row = sales_rows[0] if sales_rows else {}
    cash_sales = float(row.get("cash_sales", 0))
    total_sales = float(row.get("total_sales", 0))
    orders_count = int(row.get("orders_count", 0))
    expected_cash = round(float(s.get("opening_cash", 0)) + cash_sales, 2)
    await db.shifts.update_one({"_id": s["_id"]}, {"$set": {
        "status": "closed", "ended_at": now_iso(), "orders_count": orders_count,
        "total_cash": round(cash_sales, 2), "total_sales": round(total_sales, 2),
        "cash_sales": round(cash_sales, 2), "expected_cash": expected_cash,
        "counted_cash": round(float(body.counted_cash), 2),
        "cash_difference": round(float(body.counted_cash) - expected_cash, 2)}})
    await audit(user, "shift.end", f"{user['name']} ended shift, {orders_count} paid orders; cash difference {round(float(body.counted_cash) - expected_cash, 2)}")
    return clean(await db.shifts.find_one({"_id": s["_id"]}))


@router.get("/shifts")
async def list_shifts(skip: int = 0, limit: int = 50, user: dict = Depends(get_current_user)):
    """Managers see all shifts; cashiers only their own."""
    q = {} if is_manager(user) else {"user_id": user["id"]}
    docs = await db.shifts.find(q).sort("started_at", -1).skip(max(0, skip)).to_list(min(max(limit, 1), 100))
    return [clean(d) for d in docs]


@router.get("/reports")
async def reports(period: str = "day", start_date: str | None = None, end_date: str | None = None,
                  user: dict = Depends(require_manager)):
    """Summarize orders in Mongo using the restaurant's local calendar and business-day start."""
    settings = await get_settings_doc()
    try:
        start, end, first_day, last_day = business_range(settings, period, start_date, end_date)
    except (ValueError, KeyError):
        fail(422, "REPORT_RANGE_INVALID")
    match = {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
    summary = await db.orders.aggregate([
        {"$match": match},
        {"$group": {"_id": None, "orders_count": {"$sum": 1},
                    "paid_count": {"$sum": {"$cond": ["$paid", 1, 0]}},
                    "cancelled_count": {"$sum": {"$cond": [{"$eq": ["$status", "cancelled"]}, 1, 0]}},
                    "revenue": {"$sum": {"$cond": ["$paid", {"$ifNull": ["$restaurant_total", "$total"]}, 0]}},
                    "system_fees": {"$sum": {"$cond": ["$paid", {"$ifNull": ["$system_fee", 0]}, 0]}},
                    "system_fee_tax": {"$sum": {"$cond": ["$paid", {"$ifNull": ["$system_fee_tax", 0]}, 0]}},
                    "unpaid_count": {"$sum": {"$cond": ["$paid", 0, {"$cond": [{"$eq": ["$status", "cancelled"]}, 0, 1]}]}}}},
    ]).to_list(1)
    agg_summary = summary[0] if summary else {}
    paid_match = {**match, "paid": True}
    sellers = await db.orders.aggregate([
        {"$match": paid_match}, {"$unwind": "$items"},
        {"$group": {"_id": {"name": "$items.name", "name_en": "$items.name_en", "name_ar": "$items.name_ar"},
                    "qty": {"$sum": "$items.qty"}}}, {"$sort": {"qty": -1}},
    ]).to_list(1000)
    ranked = [{"name": row["_id"].get("name", ""), "name_en": row["_id"].get("name_en", ""),
               "name_ar": row["_id"].get("name_ar", ""), "qty": row["qty"]} for row in sellers]
    hour_rows = await db.orders.aggregate([
        {"$match": {**match, "status": {"$ne": "cancelled"}}},
        {"$addFields": {"_created": {"$dateFromString": {"dateString": "$created_at", "onError": None, "onNull": None}}}},
        {"$match": {"_created": {"$ne": None}}},
        {"$group": {"_id": {"$dateToString": {"date": "$_created", "format": "%H:00", "timezone": settings["timezone"]}}, "orders": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]).to_list(24)
    payment_rows = await db.orders.aggregate([
        {"$match": paid_match},
        {"$group": {"_id": {"$ifNull": ["$payment_method", "unknown"]}, "count": {"$sum": 1}, "total": {"$sum": {"$ifNull": ["$restaurant_total", "$total"]}}}},
        {"$sort": {"total": -1}},
    ]).to_list(10)
    cashier_rows = await db.orders.aggregate([
        {"$match": {**paid_match, "closed_by": {"$exists": True}}},
        {"$group": {"_id": {"id": "$closed_by", "name": "$closed_by_name"}, "orders": {"$sum": 1},
                    "revenue": {"$sum": {"$ifNull": ["$restaurant_total", "$total"]}}}},
        {"$sort": {"revenue": -1}},
    ]).to_list(500)
    rating = await db.ratings.aggregate([
        {"$match": {"created_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "food": {"$avg": "$food"},
                    "service": {"$avg": "$service"}, "speed": {"$avg": "$speed"}}},
    ]).to_list(1)
    revenue = round(float(agg_summary.get("revenue", 0)), 2)
    paid_count = int(agg_summary.get("paid_count", 0))
    return {
        "period": period, "start_date": first_day, "end_date": last_day,
        "orders_count": int(agg_summary.get("orders_count", 0)), "paid_count": paid_count,
        "unpaid_count": int(agg_summary.get("unpaid_count", 0)),
        "cancelled_count": int(agg_summary.get("cancelled_count", 0)),
        "revenue": revenue, "avg_order_value": round(revenue / paid_count, 2) if paid_count else 0,
        "system_fees": round(float(agg_summary.get("system_fees", 0)), 2),
        "system_fee_tax": round(float(agg_summary.get("system_fee_tax", 0)), 2),
        "best_sellers": ranked[:5], "worst_sellers": ranked[-5:][::-1],
        "busiest_hours": [{"hour": row["_id"], "orders": row["orders"]} for row in hour_rows],
        "payment_methods": [{"method": row["_id"], "orders": row["count"], "revenue": round(row["total"], 2)} for row in payment_rows],
        "cashier_performance": [{"cashier_id": row["_id"]["id"], "cashier_name": row["_id"].get("name", ""),
                                 "orders": row["orders"], "revenue": round(row["revenue"], 2)} for row in cashier_rows],
        "ratings": {"count": rating[0]["count"], "food": round(rating[0]["food"], 2),
                    "service": round(rating[0]["service"], 2), "speed": round(rating[0]["speed"], 2)} if rating else {"count": 0, "food": 0, "service": 0, "speed": 0},
    }


@router.get("/reports/me")
async def cashier_report(period: str = "day", user: dict = Depends(get_current_user)):
    """Show a cashier only their own paid-order progress and shift totals."""
    settings = await get_settings_doc()
    try:
        start, end, first_day, last_day = business_range(settings, period)
    except (ValueError, KeyError):
        fail(422, "REPORT_RANGE_INVALID")
    rows = await db.orders.aggregate([
        {"$match": {"closed_by": user["id"], "paid": True, "closed_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}}},
        {"$group": {"_id": None, "orders": {"$sum": 1}, "sales": {"$sum": {"$ifNull": ["$restaurant_total", "$total"]}},
                    "cash": {"$sum": {"$cond": [{"$eq": ["$payment_method", "cash"]}, {"$ifNull": ["$restaurant_total", "$total"]}, 0]}}}},
    ]).to_list(1)
    shifts = await db.shifts.count_documents({"user_id": user["id"], "started_at": {"$gte": start.isoformat(), "$lt": end.isoformat()}})
    row = rows[0] if rows else {}
    return {"start_date": first_day, "end_date": last_day, "orders": row.get("orders", 0),
            "sales": round(float(row.get("sales", 0)), 2), "cash": round(float(row.get("cash", 0)), 2), "shifts": shifts}


@router.get("/audit")
async def audit_list(skip: int = 0, limit: int = 50, user: dict = Depends(require_manager)):
    """Latest audit entries for managers."""
    docs = await db.audit_logs.find().sort("created_at", -1).skip(max(0, skip)).to_list(min(max(limit, 1), 100))
    return [clean(d) for d in docs]
