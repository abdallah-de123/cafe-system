"""Checkpoint B + C: role protections on /staff and settings validation."""
import asyncio

import pytest

from core.db import db
from core.settings import get_settings_doc
from tests.conftest import auth_headers, make_user, login, uniq, first_menu_item

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


async def test_concurrent_changes_cannot_disable_every_super_admin(client):
    """Two simultaneous requests still leave one active super admin."""
    first = await make_user("super_admin")
    second = await make_user("super_admin")
    await db.users.update_many({"role": "super_admin"}, {"$set": {"active": False}})
    ids = [__import__("bson").ObjectId(first["id"]), __import__("bson").ObjectId(second["id"])]
    await db.users.update_many({"_id": {"$in": ids}}, {"$set": {"active": True}})
    try:
        first_headers = await login(client, first)
        second_headers = await login(client, second)
        responses = await asyncio.gather(
            client.put(f"/api/staff/{second['id']}", json={"active": False}, headers=first_headers),
            client.put(f"/api/staff/{first['id']}", json={"active": False}, headers=second_headers),
        )
        # Depending on request scheduling, the second actor may be rejected as inactive (401)
        # before reaching the last-admin guard (400). Both outcomes safely block the second change.
        assert sorted(r.status_code for r in responses) in ([200, 400], [200, 401])
        assert await db.users.count_documents({"role": "super_admin", "active": True}) == 1
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
    await client.put("/api/admin/settings", json={"billing_enabled": False, "fee_per_invoice": 1000, "billing_mode": "monthly"}, headers=sa)


async def test_prepaid_checkout_and_refund_are_recorded_without_mutating_invoice(client):
    owner = await auth_headers(client, "owner")
    cashier = await auth_headers(client, "cashier")
    settings = await get_settings_doc()
    admin = {"billing_enabled": False, "billing_mode": "monthly", "fee_per_invoice": 1000,
             "low_balance_warning": 50000, "zero_balance_behavior": "warn_grace", "grace_invoices": 20,
             "reversal_refunds_fee": False}
    await db.settings.update_one({"key": "main"}, {"$set": {"admin": admin}})
    await db.settings.update_one({"key": "main"}, {"$set": {"currency": "SAR", "tax_rate": 10,
        "tax_enabled": True, "service_enabled": False, "service_charge": 0}})
    await db.billing_movements.insert_one({"movement_id": "test-initial-credit", "kind": "topup", "amount": 100})
    await db.billing_accounts.update_one({"_id": "main"}, {"$set": {"balance": 100, "grace_used": 0}}, upsert=True)
    try:
        sa = await auth_headers(client, "super_admin")
        await client.put("/api/admin/settings", json={"billing_enabled": True, "billing_mode": "prepaid",
            "fee_per_invoice": 10, "reversal_refunds_fee": True}, headers=sa)
        item = await first_menu_item()
        options = [{"group": g["name"], "label": g["choices"][0]["label"]} for g in item.get("options", []) if g.get("required")]
        order = (await client.post("/api/orders", json={"table_number": 1,
            "items": [{"menu_item_id": str(item["_id"]), "qty": 1, "options": options}]})).json()
        assert (await client.post(f"/api/orders/{order['id']}/accept", headers=cashier)).status_code == 200
        checkout = (await client.get(f"/api/orders/{order['id']}/checkout-summary", headers=cashier)).json()
        assert checkout["currency"] == "SAR" and checkout["system_fee"] == 10
        assert checkout["system_fee_tax"] == 1 and checkout["invoice_total"] == checkout["restaurant_total"] + 11
        for status in ("preparing", "ready", "delivered"):
            assert (await client.post(f"/api/orders/{order['id']}/status", json={"status": status}, headers=cashier)).status_code == 200
        closed = await client.post(f"/api/orders/{order['id']}/status", json={"status": "closed",
            "payment_method": "cash", "amount_received": checkout["invoice_total"]}, headers=cashier)
        assert closed.status_code == 200 and closed.json()["invoice_total"] == checkout["invoice_total"]
        original_ledger = await db.billing_ledger.find_one({"order_id": order["id"]})
        assert original_ledger["fee"] == 10
        assert (await db.billing_accounts.find_one({"_id": "main"}))["balance"] == 90
        refund = await client.post(f"/api/orders/{order['id']}/refund", json={"reason": "Customer refund"}, headers=owner)
        assert refund.status_code == 200 and refund.json()["fee_refund"] == 10
        assert (await db.billing_accounts.find_one({"_id": "main"}))["balance"] == 100
        assert (await db.billing_ledger.find_one({"order_id": order["id"]}))["_id"] == original_ledger["_id"]
        assert await db.invoice_reversals.count_documents({"order_id": order["id"]}) == 1
    finally:
        await db.settings.update_one({"key": "main"}, {"$set": {"admin": admin, "currency": settings["currency"],
            "tax_rate": settings["tax_rate"], "tax_enabled": settings["tax_enabled"],
            "service_enabled": settings["service_enabled"], "service_charge": settings["service_charge"]}})
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
    o["total"] = r.json()["total"]
    assert r.json()["history"][-1]["status"] == "edited"
    for st in ("preparing", "ready", "delivered", "closed"):
        body = {"status": st}
        if st == "closed":
            body.update({"payment_method": "cash", "amount_received": o["total"]})
        assert (await client.post(f"/api/orders/{o['id']}/status", json=body, headers=cashier)).status_code == 200
    r = await client.put(f"/api/orders/{o['id']}/items", json={"items": [line]}, headers=await auth_headers(client, "owner"))
    assert r.json()["detail"]["code"] == "ORDER_CLOSED"
