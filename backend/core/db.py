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
    await db.orders.create_index("status")
    await db.orders.create_index("accepted_by")
    await db.orders.create_index("table_number")
    await db.orders.create_index("public_token", unique=True, sparse=True)
    await db.audit_logs.create_index("created_at")
    await db.login_attempts.create_index("identifier")
    await db.ratings.create_index("order_id", unique=True)
