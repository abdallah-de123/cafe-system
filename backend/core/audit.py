"""Audit log: who did what, when. Every data-changing action writes one line here."""
from typing import Optional

from core.db import db, now_iso


async def audit(user: Optional[dict], action: str, detail: str):
    """Append an audit entry. `user` may be None for customer actions."""
    await db.audit_logs.insert_one({
        "user_id": user["id"] if user else None,
        "user_name": user["name"] if user else "customer",
        "action": action, "detail": detail, "created_at": now_iso(),
    })
