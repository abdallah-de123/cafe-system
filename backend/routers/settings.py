"""Settings routes: public read, manager update, super-admin-only section."""
from fastapi import APIRouter, Depends

from core.audit import audit
from core.db import db
from core.security import require_manager, require_super_admin
from core.settings import SettingsIn, AdminSettingsIn, get_settings_doc, get_admin_settings
from core.ws import manager

router = APIRouter(tags=["settings"])


@router.get("/settings")
async def read_settings():
    """Public settings (branding, currency, languages, tax...). Never includes admin settings."""
    return await get_settings_doc()


@router.put("/settings")
async def update_settings(body: SettingsIn, user: dict = Depends(require_manager)):
    """Owner/super admin updates public settings. Only provided (non-null) keys change."""
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.settings.update_one({"key": "main"}, {"$set": upd}, upsert=True)
        shown = {k: ("***" if k == "wifi_password" else v) for k, v in upd.items()}
        await audit(user, "settings.update", ", ".join(f"{k}={v}" for k, v in shown.items()))
    s = await get_settings_doc()
    await manager.broadcast("settings_updated", s)
    return s


@router.get("/admin/settings")
async def read_admin_settings(user: dict = Depends(require_super_admin)):
    """Super admin: license, feature flags, billing configuration."""
    return await get_admin_settings()


@router.put("/admin/settings")
async def update_admin_settings(body: AdminSettingsIn, user: dict = Depends(require_super_admin)):
    """Super admin updates the hidden settings."""
    upd = {f"admin.{k}": v for k, v in body.model_dump().items() if v is not None}
    if upd:
        await db.settings.update_one({"key": "main"}, {"$set": upd}, upsert=True)
        await audit(user, "settings.admin_update", ", ".join(f"{k}={v}" for k, v in upd.items()))
    return await get_admin_settings()
