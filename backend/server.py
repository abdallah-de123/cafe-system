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

from core.db import client, ensure_indexes  # noqa: E402
from core.settings import get_settings_doc  # noqa: E402
from routers import auth, staff, menu, orders, calls, shifts, settings as settings_router, ws  # noqa: E402
from seed import seed_super_admin, remove_demo_accounts, seed_demo_menu, migrate_users  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("restos")


async def init_db():
    """Everything the database needs before serving requests. Idempotent; also used by tests."""
    await ensure_indexes()
    await get_settings_doc()
    await migrate_users()
    await remove_demo_accounts()
    await seed_super_admin()
    await seed_demo_menu()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup tasks, serve, then close the Mongo client."""
    await init_db()
    logger.info("REST-OS startup complete")
    yield
    client.close()


app = FastAPI(lifespan=lifespan)

# All HTTP routes live under /api so the ingress can route them to the backend.
api = APIRouter(prefix="/api")
for r in (auth.router, staff.router, menu.router, orders.router, calls.router, shifts.router, settings_router.router):
    api.include_router(r)
app.include_router(api)
app.include_router(ws.router)

# CORS: explicit origins from .env. A wildcard is tolerated (we use Bearer tokens, not cookies)
# but then credentials are disabled, as browsers require.
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if not _origins or "*" in _origins:
    logger.warning("CORS_ORIGINS not set explicitly; allowing all origins without credentials")
    _origins, _creds = ["*"], False
else:
    _creds = True
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=_creds,
                   allow_methods=["*"], allow_headers=["*"])
