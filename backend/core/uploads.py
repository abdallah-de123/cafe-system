"""Validate, optimize, store, and safely remove restaurant image uploads."""
from io import BytesIO
from pathlib import Path
import re
import uuid
import warnings
from urllib.parse import urlsplit

from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool


UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "uploads"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_EDGE = 1200
THUMBNAIL_EDGE = 320
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_ASSET_NAME = re.compile(r"^(?P<id>[a-f0-9]{32})(?:_thumb)?\.webp$")


class ImageUploadError(ValueError):
    """A safe, user-facing reason that an uploaded image could not be accepted."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _encode_image(image: Image.Image, edge: int, quality: int) -> bytes:
    """Resize one image and encode it as a compact WebP while preserving transparency."""
    image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    output = BytesIO()
    image.save(output, format="WEBP", quality=quality, method=4)
    return output.getvalue()


def _process_image(content: bytes) -> tuple[bytes, bytes]:
    """Reject unsafe formats and return optimized full-size and thumbnail WebP bytes."""
    if not content:
        raise ImageUploadError("IMAGE_INVALID")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageUploadError("IMAGE_TOO_LARGE")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise ImageUploadError("IMAGE_TYPE_INVALID")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ImageUploadError("IMAGE_TOO_LARGE")
                source.verify()
            with Image.open(BytesIO(content)) as source:
                source = ImageOps.exif_transpose(source)
                full = _encode_image(source.copy(), MAX_IMAGE_EDGE, 80)
                thumb = _encode_image(source.copy(), THUMBNAIL_EDGE, 74)
                return full, thumb
    except ImageUploadError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageUploadError("IMAGE_TOO_LARGE") from None
    except Exception:
        raise ImageUploadError("IMAGE_INVALID") from None


def save_image_upload(content: bytes, kind: str) -> dict:
    """Optimize and store one menu or logo upload under a random, non-user filename."""
    if kind not in {"menu", "logo"}:
        raise ImageUploadError("IMAGE_TYPE_INVALID")
    full, thumb = _process_image(content)
    folder = UPLOAD_ROOT / kind
    folder.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    image_path = folder / f"{asset_id}.webp"
    thumb_path = folder / f"{asset_id}_thumb.webp"
    try:
        image_path.write_bytes(full)
        thumb_path.write_bytes(thumb)
    except OSError:
        image_path.unlink(missing_ok=True)
        thumb_path.unlink(missing_ok=True)
        raise ImageUploadError("IMAGE_STORAGE_FAILED") from None
    return {
        "image": f"/uploads/{kind}/{image_path.name}",
        "thumbnail": f"/uploads/{kind}/{thumb_path.name}",
    }


def _asset_paths(image_url: str) -> tuple[Path, Path] | None:
    """Resolve only our generated upload URLs; external URLs never become filesystem paths."""
    parsed = urlsplit(image_url or "")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "uploads" or parts[1] not in {"menu", "logo"}:
        return None
    match = _ASSET_NAME.fullmatch(parts[2])
    if not match:
        return None
    folder = UPLOAD_ROOT / parts[1]
    asset_id = match.group("id")
    return folder / f"{asset_id}.webp", folder / f"{asset_id}_thumb.webp"


def thumbnail_url(image_url: str) -> str:
    """Return the matching thumbnail URL for an uploaded image, or the original URL."""
    paths = _asset_paths(image_url)
    if not paths:
        return image_url or ""
    return f"{image_url.rsplit('/', 1)[0]}/{paths[1].name}"


def delete_image_upload(image_url: str) -> bool:
    """Remove only generated files inside this app's uploads folder."""
    paths = _asset_paths(image_url)
    if not paths:
        return False
    for path in paths:
        path.unlink(missing_ok=True)
    return True


async def cleanup_image_if_unused(image_url: str) -> None:
    """Delete an old upload only after no menu item or restaurant logo still references it."""
    thumb = thumbnail_url(image_url)
    if not image_url or thumb == image_url:
        return
    # Import here so this image helper does not make database setup depend on Pillow.
    from core.db import db

    refs = {"$or": [{"image": image_url}, {"image_thumbnail": image_url},
                    {"image": thumb}, {"image_thumbnail": thumb}]}
    if await db.menu_items.find_one(refs, {"_id": 1}):
        return
    logo_refs = {"key": "main", "$or": [{"logo": image_url}, {"logo_thumbnail": image_url},
                                        {"logo": thumb}, {"logo_thumbnail": thumb}]}
    if await db.settings.find_one(logo_refs, {"_id": 1}):
        return
    await run_in_threadpool(delete_image_upload, image_url)
