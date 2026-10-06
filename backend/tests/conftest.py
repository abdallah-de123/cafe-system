"""Test setup: isolated database + in-process HTTP client.

The tests NEVER touch the real database. Before importing the app we point DB_NAME to a test
database, disable rate limits (one test re-enables them explicitly), and set a test super admin.
Every test creates its own users with unique emails so the two xdist workers do not collide.
"""
import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
# One isolated database per xdist worker, so parallel workers never share state.
TEST_DB = f"restos_test_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"
assert not os.environ.get("DB_NAME", "").startswith("restos_test"), "test db must differ from the real one"
os.environ["DB_NAME"] = TEST_DB
os.environ["RATE_LIMITS_ENABLED"] = "false"
os.environ["SEED_DEMO"] = "true"
os.environ["ADMIN_EMAIL"] = "superadmin-test@example.com"
os.environ["ADMIN_PASSWORD"] = "SuperSecret#123"

import httpx  # noqa: E402
from pymongo import MongoClient  # noqa: E402

import server  # noqa: E402
from core.db import db  # noqa: E402
from core.security import hash_password  # noqa: E402


@pytest.fixture(scope="module")
def anyio_backend():
    """One asyncio loop per test module (Motor needs a stable loop)."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _reset_test_db():
    """Start from an empty test database (sync pymongo, runs once per worker)."""
    MongoClient(os.environ["MONGO_URL"]).drop_database(TEST_DB)


@pytest.fixture(scope="module")
async def client():
    """HTTP client talking to the FastAPI app in-process, after startup tasks ran."""
    await server.init_db()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as c:
        yield c


def uniq(prefix="u"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


async def make_user(role="cashier", password="Passw0rd!xyz", active=True):
    """Insert a user directly (tests must not depend on the staff API to exist)."""
    email = uniq(role)
    r = await db.users.insert_one({"email": email, "password_hash": hash_password(password), "name": role.title(),
                                   "role": role, "active": active, "token_version": 0, "deleted_at": None,
                                   "created_at": "2026-01-01T00:00:00+00:00"})
    return {"id": str(r.inserted_id), "email": email, "password": password, "role": role}


async def login(client, user):
    r = await client.post("/api/auth/login", json={"email": user["email"], "password": user["password"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def auth_headers(client, role="cashier"):
    """Create a user of `role` and return their auth headers."""
    return await login(client, await make_user(role))


async def first_menu_item():
    return await db.menu_items.find_one({"available": True})
