"""Staff management with role protections.

Rules (enforced here, not only in the UI):
- super_admin manages everyone; owner manages cashiers only; cashiers manage nobody.
- Owners cannot even see super admins.
- Nobody can deactivate / delete / demote themselves.
- The last active super admin can never be deactivated, deleted, or demoted.
- Deleting a cashier is permanent only if they have no orders/shifts; otherwise they are anonymized.
"""
from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import (require_manager, hash_password, normalize_email, validate_password_or_fail,
                           MANAGEABLE, DEMO_EMAILS, bump_token_version)
from models import StaffIn, StaffUpdate

router = APIRouter(prefix="/staff", tags=["staff"])


def _public(u: dict) -> dict:
    """Strip internal fields before returning a user."""
    u = clean(u)
    u.pop("token_version", None)
    return u


async def _get_target(sid: str, actor: dict) -> dict:
    """Load the target user and check the actor is allowed to manage that role."""
    target = await db.users.find_one({"_id": oid(sid)})
    if not target or target.get("deleted_at"):
        fail(404, "USER_NOT_FOUND")
    if target["role"] not in MANAGEABLE[actor["role"]]:
        fail(403, "CANNOT_MANAGE_ROLE")
    return target


async def _is_last_super_admin(target: dict) -> bool:
    """True if this user is the only active super admin left."""
    if target["role"] != "super_admin" or not target.get("active", True):
        return False
    others = await db.users.count_documents({
        "role": "super_admin", "active": True, "deleted_at": None, "_id": {"$ne": target["_id"]}})
    return others == 0


@router.get("")
async def list_staff(user: dict = Depends(require_manager)):
    """List staff. Owners never see super admins. Deleted (anonymized) users are hidden."""
    q = {"deleted_at": None}
    if user["role"] == "owner":
        q["role"] = {"$ne": "super_admin"}
    docs = await db.users.find(q).sort("created_at", 1).to_list(500)
    return [_public(d) for d in docs]


@router.post("")
async def create_staff(body: StaffIn, user: dict = Depends(require_manager)):
    """Create a staff account. Email must be real and unique; password must pass the rules."""
    if body.role not in MANAGEABLE[user["role"]]:
        fail(403, "CANNOT_MANAGE_ROLE")
    email = normalize_email(body.email)
    if email in DEMO_EMAILS:
        fail(422, "EMAIL_INVALID")
    await validate_password_or_fail(body.password)
    if await db.users.find_one({"email": email}):
        fail(400, "EMAIL_TAKEN")
    doc = {"name": body.name.strip(), "email": email, "password_hash": hash_password(body.password),
           "role": body.role, "active": True, "token_version": 0, "deleted_at": None,
           "created_at": now_iso(), "created_by": user["id"]}
    r = await db.users.insert_one(doc)
    await audit(user, "staff.create", f"created {body.role} {email}")
    return _public(await db.users.find_one({"_id": r.inserted_id}))


@router.put("/{sid}")
async def update_staff(sid: str, body: StaffUpdate, user: dict = Depends(require_manager)):
    """Rename, (de)activate, reset password, or change role, with all the protections above."""
    target = await _get_target(sid, user)
    is_self = str(target["_id"]) == user["id"]
    upd = {}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.active is not None and body.active != target.get("active", True):
        if not body.active:
            if is_self:
                fail(400, "CANNOT_MODIFY_SELF")
            if await _is_last_super_admin(target):
                fail(400, "LAST_SUPER_ADMIN")
        upd["active"] = body.active
    if body.role is not None and body.role != target["role"]:
        if is_self:
            fail(400, "CANNOT_MODIFY_SELF")
        if body.role not in MANAGEABLE[user["role"]]:
            fail(403, "CANNOT_MANAGE_ROLE")
        if await _is_last_super_admin(target):
            fail(400, "LAST_SUPER_ADMIN")
        upd["role"] = body.role
    if body.password:
        await validate_password_or_fail(body.password)
        upd["password_hash"] = hash_password(body.password)
    if not upd:
        return _public(target)
    await db.users.update_one({"_id": target["_id"]}, {"$set": upd})
    # Deactivation, role change, or password reset must kill existing sessions.
    if "active" in upd or "role" in upd or "password_hash" in upd:
        await bump_token_version(str(target["_id"]))
    changed = [k if k != "password_hash" else "password" for k in upd]
    await audit(user, "staff.update", f"updated {target['email']}: {changed}")
    return _public(await db.users.find_one({"_id": target["_id"]}))


@router.delete("/{sid}")
async def delete_staff(sid: str, user: dict = Depends(require_manager)):
    """Remove a staff member. Hard delete if they left no trace; otherwise anonymize and deactivate."""
    target = await _get_target(sid, user)
    if str(target["_id"]) == user["id"]:
        fail(400, "CANNOT_MODIFY_SELF")
    if await _is_last_super_admin(target):
        fail(400, "LAST_SUPER_ADMIN")
    uid = str(target["_id"])
    has_history = (await db.orders.count_documents({"accepted_by": uid}) > 0
                   or await db.shifts.count_documents({"user_id": uid}) > 0)
    if has_history:
        # Keep the id so order/shift history still resolves, but remove personal data and access.
        await db.users.update_one({"_id": target["_id"]}, {"$set": {
            "name": f"{target['name']} (deleted)", "email": f"deleted+{uid}@deleted.invalid",
            "active": False, "deleted_at": now_iso(), "password_hash": ""},
            "$inc": {"token_version": 1}})
        await audit(user, "staff.delete", f"anonymized {target['email']} (had history)")
        return {"ok": True, "mode": "anonymized"}
    await db.users.delete_one({"_id": target["_id"]})
    await audit(user, "staff.delete", f"deleted {target['email']}")
    return {"ok": True, "mode": "deleted"}
