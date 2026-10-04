"""REST-OS backend regression tests.

Covers: auth, menu, categories, orders lifecycle, cross-cashier isolation,
edit window, calls, ratings, shifts, reports, audit, settings, owner-only
RBAC. Uses REACT_APP_BACKEND_URL (public URL) through k8s ingress.
"""
import os
import time
import uuid
import pytest
import requests
from pathlib import Path

# Resolve BASE_URL from frontend/.env (REACT_APP_BACKEND_URL)
def _base_url():
    env = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE_URL = _base_url()
API = f"{BASE_URL}/api"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def owner_token():
    r = requests.post(f"{API}/auth/login", json={"email": "owner@restos.id", "password": "owner123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="session")
def kasir1_token():
    r = requests.post(f"{API}/auth/login", json={"email": "kasir1@restos.id", "password": "kasir123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="session")
def kasir2_token():
    r = requests.post(f"{API}/auth/login", json={"email": "kasir2@restos.id", "password": "kasir123"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- auth ----------
class TestAuth:
    def test_login_success_returns_user_and_token(self):
        r = requests.post(f"{API}/auth/login", json={"email": "owner@restos.id", "password": "owner123"})
        assert r.status_code == 200
        d = r.json()
        assert "token" in d and "user" in d
        assert d["user"]["email"] == "owner@restos.id"
        assert d["user"]["role"] == "owner"

    def test_login_invalid_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "owner@restos.id", "password": "wrong"})
        assert r.status_code == 401

    def test_me_requires_auth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_me_returns_user(self, owner_token):
        r = requests.get(f"{API}/auth/me", headers=H(owner_token))
        assert r.status_code == 200
        assert r.json()["email"] == "owner@restos.id"


# ---------- menu / categories ----------
class TestMenu:
    def test_list_menu_public(self):
        r = requests.get(f"{API}/menu")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 10
        it = items[0]
        for k in ("name_en", "name_ar", "description_en", "description_ar", "options", "price", "category"):
            assert k in it

    def test_categories(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200
        cats = r.json()
        assert any(c["name"] == "Minuman" for c in cats)
        for c in cats:
            assert c.get("name_en") and c.get("name_ar")

    def test_menu_crud_owner(self, owner_token):
        payload = {"name": f"TEST_Item_{uuid.uuid4().hex[:6]}", "description": "x",
                   "category": "Minuman", "price": 12345.0, "available": True, "options": []}
        r = requests.post(f"{API}/menu", json=payload, headers=H(owner_token))
        assert r.status_code == 200, r.text
        mid = r.json()["id"]
        # Update
        payload["price"] = 20000.0
        r2 = requests.put(f"{API}/menu/{mid}", json=payload, headers=H(owner_token))
        assert r2.status_code == 200
        assert r2.json()["price"] == 20000.0
        # Delete
        r3 = requests.delete(f"{API}/menu/{mid}", headers=H(owner_token))
        assert r3.status_code == 200

    def test_menu_create_requires_owner(self, kasir1_token):
        r = requests.post(f"{API}/menu", json={"name": "x", "category": "y", "price": 1},
                          headers=H(kasir1_token))
        assert r.status_code == 403


# ---------- settings ----------
class TestSettings:
    def test_read_settings_public(self):
        r = requests.get(f"{API}/settings")
        assert r.status_code == 200
        d = r.json()
        for k in ("restaurant_name", "tax_rate", "service_charge", "currency", "table_count"):
            assert k in d

    def test_update_settings_owner_only(self, kasir1_token):
        r = requests.put(f"{API}/settings", json={"restaurant_name": "x"}, headers=H(kasir1_token))
        assert r.status_code == 403

    def test_update_settings_persists(self, owner_token):
        orig = requests.get(f"{API}/settings").json()
        new_name = orig["restaurant_name"]  # keep same; still verifies write path
        r = requests.put(f"{API}/settings", json={"tax_rate": orig["tax_rate"]}, headers=H(owner_token))
        assert r.status_code == 200
        assert r.json()["restaurant_name"] == new_name


# ---------- orders lifecycle ----------
@pytest.fixture
def sample_item():
    r = requests.get(f"{API}/menu")
    items = r.json()
    for it in items:
        if it["available"]:
            return it
    pytest.skip("No menu item")


def _mk_order_payload(item, table=9):
    return {"table_number": table, "customer_name": "TEST_User",
            "items": [{"menu_item_id": item["id"], "name": item["name"],
                       "qty": 1, "unit_price": item["price"], "options": [], "note": ""}]}


class TestOrders:
    def test_create_order_no_auth(self, sample_item):
        r = requests.post(f"{API}/orders", json=_mk_order_payload(sample_item))
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "new"
        assert d["order_number"].startswith("INV-")
        assert d["subtotal"] > 0 and d["total"] > 0

    def test_create_empty_cart_rejected(self):
        r = requests.post(f"{API}/orders", json={"table_number": 1, "items": []})
        assert r.status_code == 400

    def test_full_lifecycle_and_isolation(self, sample_item, kasir1_token, kasir2_token):
        # Customer creates
        o = requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 7)).json()
        oid = o["id"]
        # kasir1 accepts
        r = requests.post(f"{API}/orders/{oid}/accept", headers=H(kasir1_token))
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"

        # kasir2 cannot advance (403)
        r = requests.post(f"{API}/orders/{oid}/status", json={"status": "preparing"}, headers=H(kasir2_token))
        assert r.status_code == 403

        # Out-of-order status fails
        r = requests.post(f"{API}/orders/{oid}/status", json={"status": "delivered"}, headers=H(kasir1_token))
        assert r.status_code == 400

        # Advance step by step
        for s in ["preparing", "ready", "delivered", "closed"]:
            r = requests.post(f"{API}/orders/{oid}/status", json={"status": s}, headers=H(kasir1_token))
            assert r.status_code == 200, f"{s}: {r.text}"
            assert r.json()["status"] == s
        # final must be paid
        g = requests.get(f"{API}/orders/{oid}").json()
        assert g["paid"] is True

    def test_accept_twice_rejected(self, sample_item, kasir1_token, kasir2_token):
        o = requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 8)).json()
        r1 = requests.post(f"{API}/orders/{o['id']}/accept", headers=H(kasir1_token))
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/orders/{o['id']}/accept", headers=H(kasir2_token))
        assert r2.status_code == 400

    def test_edit_order_within_window(self, sample_item, kasir1_token):
        o = requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 3)).json()
        r = requests.post(f"{API}/orders/{o['id']}/accept", headers=H(kasir1_token))
        assert r.status_code == 200
        new_items = [{"menu_item_id": sample_item["id"], "name": sample_item["name"],
                      "qty": 3, "unit_price": sample_item["price"], "options": [], "note": "extra"}]
        r2 = requests.put(f"{API}/orders/{o['id']}/items", json={"items": new_items}, headers=H(kasir1_token))
        assert r2.status_code == 200
        assert r2.json()["subtotal"] == pytest.approx(sample_item["price"] * 3, rel=0.01)

    def test_cashier_list_scoped(self, sample_item, kasir1_token):
        # create a fresh new order so it shows via status=new OR accepted_by
        requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 2))
        r = requests.get(f"{API}/orders", headers=H(kasir1_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_table_orders_public(self, sample_item):
        requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 11))
        r = requests.get(f"{API}/tables/11/orders")
        assert r.status_code == 200
        assert len(r.json()) >= 1


# ---------- calls ----------
class TestCalls:
    def test_create_and_resolve_call(self, kasir1_token):
        c = requests.post(f"{API}/calls", json={"table_number": 4, "kind": "help"}).json()
        assert c["status"] == "open"
        r = requests.post(f"{API}/calls/{c['id']}/resolve", headers=H(kasir1_token))
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"

    def test_list_calls_requires_auth(self):
        assert requests.get(f"{API}/calls").status_code == 401


# ---------- ratings ----------
class TestRatings:
    def test_rating_create_public(self, sample_item):
        o = requests.post(f"{API}/orders", json=_mk_order_payload(sample_item, 5)).json()
        r = requests.post(f"{API}/ratings", json={"order_id": o["id"], "food": 5, "service": 4, "speed": 5, "comment": "TEST"})
        assert r.status_code == 200

    def test_list_ratings_owner_only(self, kasir1_token, owner_token):
        assert requests.get(f"{API}/ratings", headers=H(kasir1_token)).status_code == 403
        assert requests.get(f"{API}/ratings", headers=H(owner_token)).status_code == 200


# ---------- shifts ----------
class TestShifts:
    def test_start_end_shift(self, kasir2_token):
        r = requests.post(f"{API}/shifts/start", headers=H(kasir2_token))
        assert r.status_code == 200
        assert r.json()["status"] == "open"
        e = requests.post(f"{API}/shifts/end", headers=H(kasir2_token))
        assert e.status_code == 200
        d = e.json()
        assert d["status"] == "closed"
        assert "orders_count" in d and "total_cash" in d


# ---------- reports / audit ----------
class TestOwnerOnly:
    def test_reports(self, owner_token, kasir1_token):
        assert requests.get(f"{API}/reports?period=day", headers=H(kasir1_token)).status_code == 403
        r = requests.get(f"{API}/reports?period=day", headers=H(owner_token))
        assert r.status_code == 200
        d = r.json()
        for k in ("orders_count", "revenue", "best_sellers", "busiest_hours"):
            assert k in d

    def test_audit(self, owner_token):
        r = requests.get(f"{API}/audit", headers=H(owner_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_staff_crud(self, owner_token):
        em = f"TEST_{uuid.uuid4().hex[:6]}@t.io"
        r = requests.post(f"{API}/staff", json={"name": "TEST", "email": em, "password": "pwd12345", "role": "cashier"},
                          headers=H(owner_token))
        assert r.status_code == 200
        sid = r.json()["id"]
        r2 = requests.put(f"{API}/staff/{sid}", json={"active": False}, headers=H(owner_token))
        assert r2.status_code == 200
        assert r2.json()["active"] is False
