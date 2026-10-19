"""Database connection and small document helpers used everywhere."""
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

# One Mongo client for the whole process. DB_NAME comes from .env (tests override it before import).
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


def now_iso() -> str:
    """Current UTC time as an ISO string (we store all timestamps as strings)."""
    return datetime.now(timezone.utc).isoformat()


def oid(v: str) -> ObjectId:
    """Convert a string id to ObjectId, or answer 400 if the string is not a valid id."""
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ID"})


def clean(doc: Optional[dict]) -> Optional[dict]:
    """Make a Mongo document safe to return: _id -> id (string) and drop the password hash."""
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    d.pop("password_hash", None)
    return d


async def ensure_indexes():
    """Create the indexes the app relies on. Safe to call on every startup."""
    await db.users.create_index("email", unique=True)
    await db.orders.create_index("created_at")
    # The counter generates numbers atomically; this unique index is the final database guard.
    # Sparse keeps legacy orders without an order_number valid during a safe migration.
    await db.orders.create_index("order_number", unique=True, sparse=True)
    await db.orders.create_index("status")
    await db.orders.create_index("accepted_by")
    await db.orders.create_index("table_number")
    await db.orders.create_index([("closed_at", 1), ("paid", 1)])
    await db.orders.create_index("public_token", unique=True, sparse=True)
    await db.audit_logs.create_index("created_at")
    await db.login_attempts.create_index("identifier")
    await db.ratings.create_index("order_id", unique=True)
    # Stock screens and movement history use these indexed fields as inventory grows.
    await db.inventory_items.create_index("active")
    await db.inventory_movements.create_index([("inventory_item_id", 1), ("created_at", -1)])
    await db.inventory_alerts.create_index(
        "inventory_item_id", unique=True, partialFilterExpression={"active": True}
    )
    await db.shifts.create_index("started_at")
    await db.shifts.create_index("user_id")
    await db.billing_ledger.create_index("order_id", unique=True)
    await db.billing_ledger.create_index([("closed_at", 1), ("mode", 1)])
    await db.billing_movements.create_index("movement_id", unique=True, sparse=True)
    await db.billing_movements.create_index("order_id")
    await db.billing_movements.create_index("created_at")
    await db.billing_month_payments.create_index("month", unique=True)
    await db.invoice_reversals.create_index("reversal_id", unique=True)
    await db.invoice_reversals.create_index([("order_id", 1), ("created_at", -1)])
