"""Authenticated image upload endpoints for menu items and restaurant branding."""
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from core.audit import audit
from core.db import db
from core.errors import fail
from core.security import require_manager
from core.uploads import ImageUploadError, delete_image_upload, save_image_upload, thumbnail_url
from models import ImageDeleteIn

router = APIRouter(tags=["uploads"])


@router.post("/uploads/images")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    kind: str = Form(...),
    user: dict = Depends(require_manager),
):
    """Accept a menu or logo image, optimize it off the event loop, then return public URLs."""
    if kind not in {"menu", "logo"}:
        fail(422, "IMAGE_TYPE_INVALID")
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    try:
        images = await run_in_threadpool(save_image_upload, content, kind)
    except ImageUploadError as exc:
        fail(413 if exc.code == "IMAGE_TOO_LARGE" else 422, exc.code)
    base = str(request.base_url).rstrip("/")
    result = {key: f"{base}{path}" for key, path in images.items()}
    await audit(user, "image.upload", f"uploaded {kind} image")
    return result


@router.delete("/uploads/images")
async def discard_image(body: ImageDeleteIn, user: dict = Depends(require_manager)):
    """Delete an unused upload, for example when the owner cancels an unsaved menu edit."""
    if not thumbnail_url(body.image) or thumbnail_url(body.image) == body.image:
        fail(404, "IMAGE_NOT_FOUND")
    thumb = thumbnail_url(body.image)
    used = await db.menu_items.find_one(
        {"$or": [{"image": body.image}, {"image_thumbnail": body.image},
                 {"image": thumb}, {"image_thumbnail": thumb}]}, {"_id": 1}
    )
    settings = await db.settings.find_one(
        {"key": "main", "$or": [{"logo": body.image}, {"logo_thumbnail": body.image},
                                 {"logo": thumb}, {"logo_thumbnail": thumb}]}, {"_id": 1}
    )
    if used or settings:
        fail(409, "IMAGE_IN_USE")
    removed = await run_in_threadpool(delete_image_upload, body.image)
    if not removed:
        fail(404, "IMAGE_NOT_FOUND")
    await audit(user, "image.discard", "removed an unused image upload")
    return {"ok": True}
