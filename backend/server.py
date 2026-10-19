"""REST-OS backend entry point.

Wires the FastAPI app together: loads .env, registers routers (all under /api), configures CORS,
and runs startup tasks (indexes, settings, seeding, migrations) through the lifespan handler.
Business logic lives in `routers/`, shared helpers in `core/`, request models in `models.py`.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os  # noqa: E402
import logging  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI, APIRouter  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from core.db import client, db, ensure_indexes  # noqa: E402
from core.settings import get_settings_doc  # noqa: E402
from routers import auth, staff, menu, orders, calls, shifts, settings as settings_router, uploads, ws, inventory  # noqa: E402
from core.uploads import UPLOAD_ROOT  # noqa: E402
from core.inventory import refresh_inventory_alerts, sync_menu_availability  # noqa: E402
from core.billing import reconcile_prepaid_ledger  # noqa: E402
from seed import seed_super_admin, remove_demo_accounts, seed_demo_menu, migrate_users  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restos")


async def init_db():
    """Everything the database needs before serving requests. Idempotent; also used by tests."""
    await ensure_indexes()
    await get_settings_doc()
    # Replace the previous built-in fee default on inactive copies; enabled billing is never rewritten.
    settings_doc = await db.settings.find_one({"key": "main"}) or {}
    admin_doc = settings_doc.get("admin") or {}
    if not admin_doc.get("billing_enabled") and admin_doc.get("fee_per_invoice") == 2500:
        await db.settings.update_one({"key": "main"}, {"$set": {"admin.fee_per_invoice": 1000}})
    await migrate_users()
    await remove_demo_accounts()
    await seed_super_admin()
    await seed_demo_menu()
    await refresh_inventory_alerts()
    await sync_menu_availability()
    await reconcile_prepaid_ledger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup tasks, serve, then close the Mongo client."""
    await init_db()
    logger.info("REST-OS startup complete")
    yield
    client.close()


app = FastAPI(lifespan=lifespan)

# Keep optimized menu and logo images available to customers without database reads.
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploaded_file")

# All HTTP routes live under /api so the ingress can route them to the backend.
api = APIRouter(prefix="/api")
for r in (auth.router, staff.router, menu.router, orders.router, calls.router, shifts.router,
          settings_router.router, uploads.router, inventory.router):
    api.include_router(r)
app.include_router(api)
app.include_router(ws.router)

# CORS: production must name each frontend origin; development may opt into a wildcard without credentials.
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
_production = os.environ.get("APP_ENV", "development").strip().lower() == "production"
if _production and (not _origins or "*" in _origins):
    raise RuntimeError("Production requires explicit frontend origins in CORS_ORIGINS")
if not _origins:
    # An empty allowlist is safe for local development and same-origin requests.
    # Deployed clients must configure their exact frontend origin in CORS_ORIGINS.
    logger.warning("CORS_ORIGINS is empty; cross-origin browser requests are disabled")
    _creds = False
elif "*" in _origins:
    logger.warning("Wildcard CORS is enabled for development only; credentials are disabled")
    _origins, _creds = ["*"], False
else:
    _creds = True
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=_creds,
                   allow_methods=["*"], allow_headers=["*"])
