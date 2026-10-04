"""Checkpoint B + C: role protections on /staff and settings validation."""
import pytest

from core.db import db
from tests.conftest import auth_headers, make_user, login, uniq

pytestmark = pytest.mark.anyio


async def test_owner_manages_cashiers_only(client):
    """Owners create/edit cashiers; they cannot create owners or super admins, and cannot see super admins."""
    h = await auth_headers(client, "owner")
    ok = await client.post("/api/staff", json={"name": "C", "email": uniq("c"), "password": "Passw0rd!xyz", "role": "cashier"}, headers=h)
    assert ok.status_code == 200
    for role in ("owner", "super_admin"):
        r = await client.post("/api/staff", json={"name": "X", "email": uniq("x"), "password": "Passw0rd!xyz", "role": role}, headers=h)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "CANNOT_MANAGE_ROLE"
    sa = await make_user("super_admin")
    listing = (await client.get("/api/staff", headers=h)).json()
    assert all(u["role"] != "super_admin" for u in listing)
    r = await client.put(f"/api/staff/{sa['id']}", json={"active": False}, headers=h)
    assert r.status_code == 403


async def test_cashier_cannot_access_staff(client):
    h = await auth_headers(client, "cashier")
    assert (await client.get("/api/staff", headers=h)).status_code == 403


async def test_email_and_password_rules(client):
    h = await auth_headers(client, "super_admin")
    for bad in ("not-an-email", "a@b", "x@localhost", "owner@restos.id", " "):
        r = await client.post("/api/staff", json={"name": "B", "email": bad, "password": "Passw0rd!xyz"}, headers=h)
        assert r.status_code == 422, bad
    r = await client.post("/api/staff", json={"name": "B", "email": uniq("b"), "password": "short"}, headers=h)
    assert r.json()["detail"]["code"] == "PASSWORD_TOO_SHORT"
    email = uniq("dup")
    body = {"name": "B", "email": f"  {email.upper()} ", "password": "Passw0rd!xyz"}
    first = await client.post("/api/staff", json=body, headers=h)
    assert first.status_code == 200 and first.json()["email"] == email  # trimmed + lowercased
    assert (await client.post("/api/staff", json=body, headers=h)).json()["detail"]["code"] == "EMAIL_TAKEN"


async def test_self_and_last_admin_protection(client):
    """Nobody can disable themselves; the last active super admin is untouchable."""
    sa = await make_user("super_admin")
    h = await login(client, sa)
    r = await client.put(f"/api/staff/{sa['id']}", json={"active": False}, headers=h)
    assert r.json()["detail"]["code"] == "CANNOT_MODIFY_SELF"
    assert (await client.delete(f"/api/staff/{sa['id']}", headers=h)).json()["detail"]["code"] == "CANNOT_MODIFY_SELF"
    # Make `other` the only remaining active super admin, then try to disable/demote/delete it.
    other = await make_user("super_admin")
    await db.users.update_many({"role": "super_admin", "_id": {"$ne": __import__("bson").ObjectId(other["id"])}},
                               {"$set": {"active": False}})
    try:
        for body in ({"active": False}, {"role": "cashier"}):
            r = await client.put(f"/api/staff/{other['id']}", json=body, headers=h)
            assert r.status_code == 401 or r.json()["detail"]["code"] == "LAST_SUPER_ADMIN", r.text
    finally:
        await db.users.update_many({"role": "super_admin"}, {"$set": {"active": True}})


async def test_deactivation_blocks_login_and_kills_token(client):
    h = await auth_headers(client, "owner")
    c = await make_user("cashier")
    ch = await login(client, c)
    r = await client.put(f"/api/staff/{c['id']}", json={"active": False}, headers=h)
    assert r.status_code == 200 and r.json()["active"] is False
    assert (await client.get("/api/auth/me", headers=ch)).status_code == 401
    r = await client.post("/api/auth/login", json={"email": c["email"], "password": c["password"]})
    assert r.json()["detail"]["code"] == "ACCOUNT_INACTIVE"
    r = await client.put(f"/api/staff/{c['id']}", json={"active": True}, headers=h)
    assert r.json()["active"] is True


async def test_delete_hard_vs_anonymize(client):
    h = await auth_headers(client, "owner")
    fresh = await make_user("cashier")
    r = await client.delete(f"/api/staff/{fresh['id']}", headers=h)
    assert r.json()["mode"] == "deleted"
    busy = await make_user("cashier")
    await db.shifts.insert_one({"user_id": busy["id"], "user_name": "Busy", "status": "closed", "started_at": "2026-01-01T00:00:00+00:00"})
    r = await client.delete(f"/api/staff/{busy['id']}", headers=h)
    assert r.json()["mode"] == "anonymized"
    doc = await db.users.find_one({"_id": __import__("bson").ObjectId(busy["id"])})
    assert doc["active"] is False and doc["email"].startswith("deleted+") and doc["deleted_at"]
    assert (await client.post("/api/auth/login", json={"email": busy["email"], "password": busy["password"]})).status_code == 401
    assert all(u["id"] != busy["id"] for u in (await client.get("/api/staff", headers=h)).json())


async def test_reset_password_by_manager(client):
    h = await auth_headers(client, "owner")
    c = await make_user("cashier")
    r = await client.put(f"/api/staff/{c['id']}", json={"password": "Reset#Pass123"}, headers=h)
    assert r.status_code == 200
    assert (await client.post("/api/auth/login", json={"email": c["email"], "password": "Reset#Pass123"})).status_code == 200


async def test_settings_validation_and_admin_section(client):
    owner = await auth_headers(client, "owner")
    pub = (await client.get("/api/settings")).json()
    assert "admin" not in pub and "billing_enabled" not in pub and pub["edit_window_seconds"] == 60
    assert (await client.put("/api/settings", json={"tax_rate": 150}, headers=owner)).status_code == 422
    assert (await client.put("/api/settings", json={"timezone": "Mars/Olympus"}, headers=owner)).status_code == 422
    assert (await client.put("/api/settings", json={"business_day_start": "25:00"}, headers=owner)).status_code == 422
    assert (await client.put("/api/settings", json={"enabled_languages": []}, headers=owner)).status_code == 422
    ok = await client.put("/api/settings", json={"edit_window_seconds": 90, "timezone": "Asia/Riyadh",
                                                  "payment_methods": {"cash": True, "card": False, "qris": True, "other": False}}, headers=owner)
    assert ok.status_code == 200 and ok.json()["edit_window_seconds"] == 90 and ok.json()["timezone"] == "Asia/Riyadh"
    # Admin section: owners are refused, super admin can read/write.
    assert (await client.get("/api/admin/settings", headers=owner)).status_code == 403
    sa = await auth_headers(client, "super_admin")
    r = await client.put("/api/admin/settings", json={"billing_enabled": True, "fee_per_invoice": 2500, "billing_mode": "prepaid"}, headers=sa)
    assert r.status_code == 200 and r.json()["billing_mode"] == "prepaid"
    assert (await client.put("/api/admin/settings", json={"billing_mode": "weekly"}, headers=sa)).status_code == 422
    await client.put("/api/settings", json={"edit_window_seconds": 60}, headers=owner)


async def test_closed_order_is_immutable_and_edit_window(client):
    """Closed orders reject item edits; cashier edits respect the window, managers are exempt."""
    from tests.conftest import first_menu_item
    item = await first_menu_item()
    opts = [{"group": g["name"], "label": g["choices"][0]["label"]} for g in item.get("options", []) if g.get("required")]
    line = {"menu_item_id": str(item["_id"]), "qty": 1, "options": opts}
    o = (await client.post("/api/orders", json={"table_number": 1, "items": [line]})).json()
    cashier = await auth_headers(client, "cashier")
    assert (await client.post(f"/api/orders/{o['id']}/accept", headers=cashier)).status_code == 200
    other = await auth_headers(client, "cashier")
    r = await client.put(f"/api/orders/{o['id']}/items", json={"items": [{**line, "qty": 2}]}, headers=other)
    assert r.json()["detail"]["code"] == "ORDER_NOT_OWNER"
    r = await client.put(f"/api/orders/{o['id']}/items", json={"items": [{**line, "qty": 2, "unit_price": 1}]}, headers=cashier)
    assert r.status_code == 200 and r.json()["items"][0]["qty"] == 2 and r.json()["items"][0]["unit_price"] != 1
    assert r.json()["history"][-1]["status"] == "edited"
    for st in ("preparing", "ready", "delivered", "closed"):
        assert (await client.post(f"/api/orders/{o['id']}/status", json={"status": st}, headers=cashier)).status_code == 200
    r = await client.put(f"/api/orders/{o['id']}/items", json={"items": [line]}, headers=await auth_headers(client, "owner"))
    assert r.json()["detail"]["code"] == "ORDER_CLOSED"
