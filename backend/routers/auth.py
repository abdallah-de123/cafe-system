"""Auth routes: login (with lockout), me, logout (revokes tokens), change password."""
from fastapi import APIRouter, Depends, Request

from core.audit import audit
from core.db import db, clean, oid, now_iso
from core.errors import fail
from core.security import (verify_password, hash_password, create_access_token, get_current_user,
                           bump_token_version, validate_password_or_fail, rate_limit, client_ip,
                           check_lockout, record_failure, clear_failures)
from models import LoginIn, ChangePasswordIn

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(rate_limit("login", 20))])
async def login(body: LoginIn, request: Request):
    """Email + password login. 5 failures per ip:email lock the pair for 15 minutes."""
    email = (body.email or "").lower().strip()
    identifier = f"{client_ip(request)}:{email}"
    await check_lockout(identifier)
    user = await db.users.find_one({"email": email})
    if not user or user.get("deleted_at") or not verify_password(body.password, user["password_hash"]):
        await record_failure(identifier)
        fail(401, "AUTH_INVALID_CREDENTIALS")
    if not user.get("active", True):
        fail(403, "ACCOUNT_INACTIVE")
    await clear_failures(identifier)
    u = clean(user)
    token = await create_access_token(u)
    await audit(u, "auth.login", f"{u['email']} logged in")
    u.pop("token_version", None)
    return {"user": u, "token": token}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the logged-in user."""
    user.pop("token_version", None)
    return user


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    """Revoke all tokens of this user by bumping token_version."""
    await bump_token_version(user["id"])
    await audit(user, "auth.logout", f"{user['email']} logged out")
    return {"ok": True}


@router.post("/change-password")
async def change_password(body: ChangePasswordIn, user: dict = Depends(get_current_user)):
    """Any user changes their own password. Old sessions are revoked; a fresh token is returned."""
    doc = await db.users.find_one({"_id": oid(user["id"])})
    if not verify_password(body.current_password, doc["password_hash"]):
        fail(400, "PASSWORD_CURRENT_WRONG")
    await validate_password_or_fail(body.new_password)
    if body.new_password == body.current_password:
        fail(400, "PASSWORD_SAME")
    await db.users.update_one({"_id": doc["_id"]}, {
        "$set": {"password_hash": hash_password(body.new_password), "password_changed_at": now_iso()},
        "$inc": {"token_version": 1}})
    fresh = clean(await db.users.find_one({"_id": doc["_id"]}))
    token = await create_access_token(fresh)
    await audit(user, "auth.change_password", f"{user['email']} changed own password")
    fresh.pop("token_version", None)
    return {"user": fresh, "token": token}
