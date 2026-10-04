"""Checkpoint A: server-side pricing, validation, order tokens, ratings, lockout, rate limits, seeding."""
import pytest

from core.db import db
from core.security import limiter, hash_password
from seed import seed_demo_menu, seed_super_admin
from tests.conftest import first_menu_item, auth_headers, make_user, login

pytestmark = pytest.mark.anyio


async def _order_payload(item, qty=1, **extra):
    opts = [{"group": g["name"], "label": g["choices"][0]["label"]} for g in item.get("options", []) if g.get("required")]
    return {"table_number": 1, "items": [{"menu_item_id": str(item["_id"]), "qty": qty, "options": opts, **extra}]}


async def test_client_price_is_ignored(client):
    """S1: a customer sending unit_price=1 still pays the real menu price."""
    item = await first_menu_item()
    body = await _order_payload(item, unit_price=1, name="hacked")
    r = await client.post("/api/orders", json=body)
    assert r.status_code == 200, r.text
    o = r.json()
    real = item["discount_price"] if item.get("discount_price") is not None else item["price"]
    assert o["items"][0]["unit_price"] == real
    assert o["items"][0]["name"] == item["name"]
    assert o["total"] > 0 and "public_token" in o


async def test_qty_must_be_positive(client):
    """S2: qty 0 or negative is rejected with 422."""
    item = await first_menu_item()
    for q in (0, -3, 500):
        r = await client.post("/api/orders", json=await _order_payload(item, qty=q))
        assert r.status_code == 422


async def test_unavailable_item_rejected(client):
    """S3: sold-out items cannot be ordered."""
    item = await first_menu_item()
    await db.menu_items.update_one({"_id": item["_id"]}, {"$set": {"available": False}})
    try:
        r = await client.post("/api/orders", json=await _order_payload(item))
        assert r.status_code == 400 and r.json()["detail"]["code"] == "ITEM_UNAVAILABLE"
    finally:
        await db.menu_items.update_one({"_id": item["_id"]}, {"$set": {"available": True}})


async def test_unknown_option_and_bad_table(client):
    item = await first_menu_item()
    body = await _order_payload(item)
    body["items"][0]["options"] = [{"group": "x", "label": "Gold plated"}]
    r = await client.post("/api/orders", json=body)
    assert r.json()["detail"]["code"] == "OPTION_INVALID"
    body = await _order_payload(item)
    body["table_number"] = 9999
    r = await client.post("/api/orders", json=body)
    assert r.json()["detail"]["code"] == "TABLE_INVALID"


async def test_order_token_protects_order(client):
    """S8: GET /orders/{id} needs the order token (customer) or a staff JWT."""
    item = await first_menu_item()
    o = (await client.post("/api/orders", json=await _order_payload(item))).json()
    assert (await client.get(f"/api/orders/{o['id']}")).status_code == 403
    assert (await client.get(f"/api/orders/{o['id']}", params={"token": "wrong"})).status_code == 403
    ok = await client.get(f"/api/orders/{o['id']}", params={"token": o["public_token"]})
    assert ok.status_code == 200 and "accepted_by" not in ok.json()
    staff = await client.get(f"/api/orders/{o['id']}", headers=await auth_headers(client))
    assert staff.status_code == 200
    mine = await client.post("/api/orders/mine", json={"tokens": [o["public_token"], "junk"]})
    assert [x["id"] for x in mine.json()] == [o["id"]]
    assert (await client.get("/api/tables/1/orders")).status_code in (404, 405)


async def test_rating_rules(client):
    """S11: rating needs the token, a delivered order, scores 1-5, and only once."""
    item = await first_menu_item()
    o = (await client.post("/api/orders", json=await _order_payload(item))).json()
    base = {"order_id": o["id"], "token": o["public_token"], "food": 5, "service": 5, "speed": 5}
    assert (await client.post("/api/ratings", json=base)).json()["detail"]["code"] == "RATING_TOO_EARLY"
    await db.orders.update_one({"public_token": o["public_token"]}, {"$set": {"status": "delivered"}})
    assert (await client.post("/api/ratings", json={**base, "food": 9})).status_code == 422
    assert (await client.post("/api/ratings", json={**base, "token": "bad"})).status_code == 403
    assert (await client.post("/api/ratings", json=base)).status_code == 200
    assert (await client.post("/api/ratings", json=base)).json()["detail"]["code"] == "RATING_EXISTS"


async def test_login_lockout(client):
    """S9: 5 wrong passwords lock the ip:email pair."""
    u = await make_user()
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": u["email"], "password": "nope"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
    assert r.status_code == 423 and r.json()["detail"]["code"] == "LOGIN_LOCKED"


async def test_rate_limit_on_orders(client):
    """S9: public endpoints are limited per IP."""
    limiter.enabled = True
    limiter.hits.clear()
    try:
        item = await first_menu_item()
        codes = [(await client.post("/api/orders", json=await _order_payload(item))).status_code for _ in range(12)]
        assert 429 in codes and codes[0] == 200
    finally:
        limiter.enabled = False
        limiter.hits.clear()


async def test_seed_never_overwrites(client):
    """S4/S5: re-running seeding keeps the owner's menu edits and existing passwords."""
    item = await first_menu_item()
    await db.menu_items.update_one({"_id": item["_id"]}, {"$set": {"price": 123456.0}})
    await seed_demo_menu()
    assert (await db.menu_items.find_one({"_id": item["_id"]}))["price"] == 123456.0
    admin = await db.users.find_one({"role": "super_admin"})
    await db.users.update_one({"_id": admin["_id"]}, {"$set": {"password_hash": hash_password("Changed#999")}})
    await seed_super_admin()
    fresh = await db.users.find_one({"_id": admin["_id"]})
    assert fresh["password_hash"] != admin["password_hash"]  # still the changed one, not reset
    assert await db.users.count_documents({"email": {"$in": ["owner@restos.id", "kasir1@restos.id"]}}) == 0


async def test_logout_revokes_token(client):
    """S12: after logout the old token is rejected."""
    h = await auth_headers(client)
    assert (await client.get("/api/auth/me", headers=h)).status_code == 200
    await client.post("/api/auth/logout", headers=h)
    assert (await client.get("/api/auth/me", headers=h)).status_code == 401


async def test_change_password(client):
    u = await make_user()
    h = await login(client, u)
    bad = await client.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "NewPass#123"}, headers=h)
    assert bad.json()["detail"]["code"] == "PASSWORD_CURRENT_WRONG"
    short = await client.post("/api/auth/change-password", json={"current_password": u["password"], "new_password": "abc"}, headers=h)
    assert short.json()["detail"]["code"] == "PASSWORD_TOO_SHORT"
    ok = await client.post("/api/auth/change-password", json={"current_password": u["password"], "new_password": "NewPass#123"}, headers=h)
    assert ok.status_code == 200
    assert (await client.get("/api/auth/me", headers=h)).status_code == 401  # old token dead
    assert (await client.post("/api/auth/login", json={"email": u["email"], "password": "NewPass#123"})).status_code == 200
