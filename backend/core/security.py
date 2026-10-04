"""Security: password hashing, JWT tokens, current-user lookup, role checks, rate limiting.

Tokens are HS256 JWTs sent as `Authorization: Bearer <token>`. Each token carries the user's
`token_version`; bumping that number (logout, password change, deactivation) invalidates every
token issued before, so sessions can really be revoked.
"""
import os
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Iterable, Optional

import bcrypt
import jwt
from email_validator import validate_email, EmailNotValidError
from fastapi import Depends, Request, HTTPException

from core.db import db, oid, clean, now_iso
from core.errors import fail
from core.settings import get_settings_doc

logger = logging.getLogger("restos")
JWT_ALGORITHM = "HS256"

ROLES = ("super_admin", "owner", "cashier")
# Roles a manager may create or edit. Owners manage cashiers only; super admins manage everyone.
MANAGEABLE = {"super_admin": {"super_admin", "owner", "cashier"}, "owner": {"cashier"}, "cashier": set()}

# Demo accounts from early versions. They are never (re)created, and never accepted as the super admin.
DEMO_EMAILS = {"owner@restos.id", "kasir1@restos.id", "kasir2@restos.id"}


# ---------- passwords ----------
def hash_password(p: str) -> str:
    """bcrypt hash with a fresh salt."""
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    """Constant-time bcrypt check; any error counts as a failed check."""
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


async def validate_password_or_fail(p: str):
    """Enforce the configurable minimum password length and reject blank passwords."""
    s = await get_settings_doc()
    if not p or not p.strip():
        fail(422, "PASSWORD_EMPTY")
    if len(p) < int(s["min_password_length"]):
        fail(422, "PASSWORD_TOO_SHORT", min_length=int(s["min_password_length"]))


def normalize_email(raw: str) -> str:
    """Trim + lowercase + validate email format. Rejects placeholders like 'a@b' or 'test@test'."""
    try:
        v = validate_email((raw or "").strip(), check_deliverability=False)
    except EmailNotValidError:
        fail(422, "EMAIL_INVALID")
    email = v.normalized.lower()
    local, _, domain = email.partition("@")
    # Require a real-looking domain with a TLD (blocks 'user@localhost', 'a@b').
    if "." not in domain or domain.endswith((".local", ".test", ".invalid", ".example", ".localhost")):
        fail(422, "EMAIL_INVALID")
    return email


# ---------- tokens ----------
async def create_access_token(user: dict) -> str:
    """Issue a JWT for a user; lifetime comes from settings.session_hours."""
    s = await get_settings_doc()
    payload = {
        "sub": user["id"], "email": user["email"], "role": user["role"],
        "tv": int(user.get("token_version", 0)), "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(hours=int(s["session_hours"])),
    }
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def user_from_token(token: str) -> dict:
    """Decode a token and load the live user. Rejects expired, revoked, or deactivated users."""
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        fail(401, "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        fail(401, "TOKEN_INVALID")
    if payload.get("type") != "access":
        fail(401, "TOKEN_INVALID")
    user = await db.users.find_one({"_id": oid(payload["sub"])})
    if not user or not user.get("active", True) or user.get("deleted_at"):
        fail(401, "USER_NOT_FOUND")
    if int(user.get("token_version", 0)) != int(payload.get("tv", -1)):
        fail(401, "TOKEN_REVOKED")
    return clean(user)


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: read the Bearer token and return the current user."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        fail(401, "NOT_AUTHENTICATED")
    return await user_from_token(token)


def require_roles(*roles: str):
    """Dependency factory: only let the listed roles through."""
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            fail(403, "FORBIDDEN")
        return user
    return dep


# Shortcuts used by routers.
require_manager = require_roles("super_admin", "owner")   # owner-level access
require_super_admin = require_roles("super_admin")


def is_manager(user: dict) -> bool:
    """True for owner and super admin."""
    return user["role"] in ("super_admin", "owner")


async def bump_token_version(user_id: str):
    """Invalidate every existing token of this user."""
    await db.users.update_one({"_id": oid(user_id)}, {"$inc": {"token_version": 1}})


# ---------- rate limiting ----------
class RateLimiter:
    """Tiny in-memory sliding-window limiter keyed by client IP. Good enough for one restaurant copy."""

    def __init__(self):
        self.hits: Dict[str, deque] = defaultdict(deque)
        self.enabled = os.environ.get("RATE_LIMITS_ENABLED", "true").lower() != "false"

    def check(self, key: str, limit: int, window: int):
        """Record a hit and raise 429 if `limit` hits happened inside the last `window` seconds."""
        if not self.enabled:
            return
        now = time.time()
        q = self.hits[key]
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= limit:
            fail(429, "RATE_LIMITED")
        q.append(now)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Best-effort client IP (behind the ingress we read X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window: int = 60):
    """Dependency factory: `Depends(rate_limit("orders", 10))` = 10 calls per minute per IP."""
    async def dep(request: Request):
        limiter.check(f"{name}:{client_ip(request)}", limit, window)
    return dep


# ---------- login lockout ----------
LOCKOUT_MAX_FAILS = 5
LOCKOUT_MINUTES = 15


async def check_lockout(identifier: str):
    """Raise 423 if this ip:email pair has too many recent failures."""
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if not doc:
        return
    locked_until = doc.get("locked_until")
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
        fail(423, "LOGIN_LOCKED", minutes=LOCKOUT_MINUTES)


async def record_failure(identifier: str):
    """Count a failed login; lock after LOCKOUT_MAX_FAILS."""
    doc = await db.login_attempts.find_one_and_update(
        {"identifier": identifier}, {"$inc": {"fails": 1}, "$set": {"last_at": now_iso()}},
        upsert=True, return_document=True)
    if doc and doc.get("fails", 0) >= LOCKOUT_MAX_FAILS:
        until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        await db.login_attempts.update_one({"identifier": identifier}, {"$set": {"locked_until": until, "fails": 0}})


async def clear_failures(identifier: str):
    """Forget failures after a successful login."""
    await db.login_attempts.delete_one({"identifier": identifier})
