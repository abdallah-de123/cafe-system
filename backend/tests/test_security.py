"""Checkpoint A: server pricing, validation, order tokens/numbers, ratings, lockout, and seeding."""
import asyncio
from io import BytesIO
from urllib.parse import urlsplit

import pytest
from PIL import Image

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


async def test_one_choice_per_option_group(client):
    """A crafted cart cannot add multiple choices from a single-choice menu group."""
    item = await first_menu_item()
    group = next(g for g in item.get("options", []) if len(g.get("choices", [])) > 1)
    body = await _order_payload(item)
    body["items"][0]["options"] = [
        {"group": group["name"], "label": choice["label"]} for choice in group["choices"][:2]
    ]
    r = await client.post("/api/orders", json=body)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "OPTION_DUPLICATE_GROUP"


async def test_invoice_numbers_are_unique_under_concurrent_orders(client):
    """The atomic counter and unique Mongo index keep concurrent invoice numbers distinct."""
    item = await first_menu_item()
    payload = await _order_payload(item)
    responses = await asyncio.gather(*[
        client.post("/api/orders", json=payload) for _ in range(20)
    ])
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
    numbers = [r.json()["order_number"] for r in responses]
    assert len(numbers) == len(set(numbers))
    indexes = await db.orders.index_information()
    assert any(v.get("unique") and v["key"] == [("order_number", 1)] for v in indexes.values())


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


async def test_super_admin_seed_requires_a_valid_normalized_email(client, monkeypatch):
    """The secret-provisioned super admin follows the same valid-email rule as staff accounts."""
    monkeypatch.setenv("ADMIN_EMAIL", "not-an-email")
    monkeypatch.setenv("ADMIN_PASSWORD", "ValidPass#123")
    await seed_super_admin()
    assert await db.users.find_one({"email": "not-an-email"}) is None

    monkeypatch.setenv("ADMIN_EMAIL", "  FIRST.ADMIN@EXAMPLE.COM  ")
    await seed_super_admin()
    assert await db.users.find_one({"email": "first.admin@example.com", "role": "super_admin"})


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


def _png_bytes(width=1600, height=900):
    """Create an in-memory PNG fixture for upload tests."""
    image = Image.new("RGB", (width, height), color=(194, 82, 41))
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _public_path(url):
    """Extract the app-local route used to fetch a public uploaded image."""
    return urlsplit(url).path


async def _upload_image(client, headers, kind="menu", content=None):
    """Send one multipart image to the authenticated upload endpoint."""
    return await client.post(
        "/api/uploads/images", headers=headers, data={"kind": kind},
        files={"file": ("photo.png", content if content is not None else _png_bytes(), "image/png")},
    )


async def test_menu_upload_requires_manager_and_serves_optimized_thumbnail(client):
    """Only managers can upload; generated WebP files and thumbnails are served publicly."""
    cashier = await auth_headers(client, "cashier")
    assert (await _upload_image(client, cashier)).status_code == 403

    owner = await auth_headers(client, "owner")
    response = await _upload_image(client, owner)
    assert response.status_code == 200, response.text
    result = response.json()
    full = await client.get(_public_path(result["image"]))
    thumb = await client.get(_public_path(result["thumbnail"]))
    assert full.status_code == thumb.status_code == 200
    assert full.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(full.content)) as image:
        assert image.width <= 1200 and image.height <= 1200
    with Image.open(BytesIO(thumb.content)) as image:
        assert image.width <= 320 and image.height <= 320
    removed = await client.request("DELETE", "/api/uploads/images", headers=owner, json={"image": result["image"]})
    assert removed.status_code == 200
    assert (await client.get(_public_path(result["image"]))).status_code == 404


async def test_upload_rejects_non_images_and_oversized_files(client):
    """Reject unsupported image formats and uploads that exceed five megabytes."""
    owner = await auth_headers(client, "owner")
    bmp = BytesIO()
    Image.new("RGB", (16, 16), color=(0, 0, 0)).save(bmp, format="BMP")
    invalid = await _upload_image(client, owner, content=bmp.getvalue())
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "IMAGE_TYPE_INVALID"
    oversized = await _upload_image(client, owner, content=b"x" * (5 * 1024 * 1024 + 1))
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


async def test_menu_image_replacement_and_delete_clean_old_uploads(client):
    """Replacing or removing a menu image cleans the previous optimized files."""
    owner = await auth_headers(client, "owner")
    first = (await _upload_image(client, owner)).json()
    second = (await _upload_image(client, owner)).json()
    payload = {
        "name": "Photo test item", "description": "", "name_en": "Photo test item", "name_ar": "",
        "description_en": "", "description_ar": "", "image": first["image"], "price": 1000,
        "category": "Test", "available": True, "options": [],
    }
    created = await client.post("/api/menu", headers=owner, json=payload)
    assert created.status_code == 200, created.text
    payload["image"] = second["image"]
    updated = await client.put(f"/api/menu/{created.json()['id']}", headers=owner, json=payload)
    assert updated.status_code == 200, updated.text
    assert (await client.get(_public_path(first["image"]))).status_code == 404
    deleted = await client.delete(f"/api/menu/{created.json()['id']}", headers=owner)
    assert deleted.status_code == 200
    assert (await client.get(_public_path(second["image"]))).status_code == 404


async def test_logo_replacement_cleans_old_upload_and_keeps_thumbnail(client):
    """Logo uploads use the same optimization and safe old-file cleanup as menu images."""
    owner = await auth_headers(client, "owner")
    first = (await _upload_image(client, owner, kind="logo")).json()
    saved_first = await client.put("/api/settings", headers=owner, json={"logo": first["image"]})
    assert saved_first.status_code == 200
    assert saved_first.json()["logo_thumbnail"] == first["thumbnail"]
    second = (await _upload_image(client, owner, kind="logo")).json()
    saved_second = await client.put("/api/settings", headers=owner, json={"logo": second["image"]})
    assert saved_second.status_code == 200
    assert (await client.get(_public_path(first["image"]))).status_code == 404
    assert (await client.get(_public_path(second["thumbnail"]))).status_code == 200


async def test_inventory_accept_cancel_and_auto_hide(client):
    """Accept deducts recipe stock once; cancellation returns it and restores auto-hidden menu items."""
    owner = await auth_headers(client, "owner")
    cashier = await auth_headers(client, "cashier")
    cashier_item = await client.post("/api/inventory", headers=cashier, json={
        "name": "Blocked stock", "unit": "g", "initial_quantity": 1,
    })
    assert cashier_item.status_code == 403
    stock = await client.post("/api/inventory", headers=owner, json={
        "name": "Phase 3 test stock", "name_en": "Phase 3 test stock", "unit": "g",
        "initial_quantity": 5, "low_stock_threshold": 3,
    })
    assert stock.status_code == 200, stock.text
    stock_id = stock.json()["id"]
    menu = await client.post("/api/menu", headers=owner, json={
        "name": "Phase 3 test menu", "price": 10, "category": "Test", "available": True,
        "options": [], "consumes": [{"inventory_item_id": stock_id, "qty_per_unit": 1}],
    })
    assert menu.status_code == 200, menu.text
    order = await client.post("/api/orders", json={
        "table_number": 1, "items": [{"menu_item_id": menu.json()["id"], "qty": 5}],
    })
    assert order.status_code == 200, order.text
    accepted = await client.post(f"/api/orders/{order.json()['id']}/accept", headers=cashier)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["items"][0].get("inventory_requirements") is not None
    assert (await db.inventory_items.find_one({"_id": __import__("bson").ObjectId(stock_id)}))["quantity"] == 0
    hidden = await db.menu_items.find_one({"_id": __import__("bson").ObjectId(menu.json()["id"])})
    assert hidden["available"] is False and hidden["inventory_auto_hidden"] is True
    active_alert = await db.inventory_alerts.find_one({"inventory_item_id": stock_id, "active": True})
    assert active_alert is not None

    cancelled = await client.post(f"/api/orders/{order.json()['id']}/cancel", headers=cashier, json={"reason": "Customer changed mind"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert (await db.inventory_items.find_one({"_id": __import__("bson").ObjectId(stock_id)}))["quantity"] == 5
    restored = await db.menu_items.find_one({"_id": __import__("bson").ObjectId(menu.json()["id"])})
    assert restored["available"] is True and "inventory_auto_hidden" not in restored
    assert await db.inventory_alerts.count_documents({"inventory_item_id": stock_id, "active": True}) == 0
    kinds = await db.inventory_movements.distinct("kind", {"order_id": order.json()["id"]})
    assert set(kinds) == {"sale", "cancel_return"}


async def test_inventory_insufficient_stock_does_not_accept_order(client):
    """An order with an insufficient recipe remains new and does not partially deduct stock."""
    owner = await auth_headers(client, "owner")
    cashier = await auth_headers(client, "cashier")
    stock = (await client.post("/api/inventory", headers=owner, json={
        "name": "Low test stock", "unit": "ml", "initial_quantity": 1,
    })).json()
    menu = await client.post("/api/menu", headers=owner, json={
        "name": "Low stock test menu", "price": 10, "category": "Test", "available": True,
        "options": [], "consumes": [{"inventory_item_id": stock["id"], "qty_per_unit": 1}],
    })
    assert menu.status_code == 200, menu.text
    order = await client.post("/api/orders", json={
        "table_number": 1, "items": [{"menu_item_id": menu.json()["id"], "qty": 2}],
    })
    assert order.status_code == 200
    result = await client.post(f"/api/orders/{order.json()['id']}/accept", headers=cashier)
    assert result.status_code == 409 and result.json()["detail"]["code"] == "INVENTORY_STOCK_INSUFFICIENT"
    saved_order = await db.orders.find_one({"_id": __import__("bson").ObjectId(order.json()["id"])})
    saved_stock = await db.inventory_items.find_one({"_id": __import__("bson").ObjectId(stock["id"])})
    assert saved_order["status"] == "new" and saved_stock["quantity"] == 1
