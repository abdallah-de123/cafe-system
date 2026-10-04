from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import jwt
import bcrypt
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, Field

client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]

app = FastAPI()
api = APIRouter(prefix="/api")
logger = logging.getLogger("restos")
logging.basicConfig(level=logging.INFO)

JWT_ALGORITHM = "HS256"
STATUS_FLOW = ["new", "accepted", "preparing", "ready", "delivered", "closed"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def oid(v: str) -> ObjectId:
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def clean(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    d.pop("password_hash", None)
    return d


# ---------------- auth ----------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {"sub": user_id, "email": email, "role": role,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"_id": oid(payload["sub"])})
    if not user or not user.get("active", True):
        raise HTTPException(status_code=401, detail="User not found")
    return clean(user)


async def require_owner(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


# ---------------- websockets ----------------
class Manager:
    def __init__(self):
        self.conns: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.conns:
            self.conns.remove(ws)

    async def broadcast(self, event: str, data: Any):
        msg = {"event": event, "data": data}
        for ws in list(self.conns):
            try:
                await ws.send_json(msg)
            except Exception:
                self.disconnect(ws)


manager = Manager()


@app.websocket("/api/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


async def audit(user: Optional[dict], action: str, detail: str):
    await db.audit_logs.insert_one({
        "user_id": user["id"] if user else None,
        "user_name": user["name"] if user else "customer",
        "action": action, "detail": detail, "created_at": now_iso(),
    })


# ---------------- models ----------------
class LoginIn(BaseModel):
    email: str
    password: str


class OptionChoice(BaseModel):
    label: str
    price_delta: float = 0


class OptionGroup(BaseModel):
    name: str
    required: bool = False
    choices: List[OptionChoice] = []


class MenuItemIn(BaseModel):
    name: str
    description: str = ""
    image: str = ""
    price: float
    discount_price: Optional[float] = None
    category: str
    available: bool = True
    options: List[OptionGroup] = []


class StaffIn(BaseModel):
    name: str
    email: str
    password: str
    role: str = "cashier"


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class CartItemIn(BaseModel):
    menu_item_id: str
    name: str
    qty: int = 1
    unit_price: float
    options: List[Dict[str, Any]] = []
    note: str = ""


class OrderIn(BaseModel):
    table_number: int
    items: List[CartItemIn]
    customer_name: str = ""


class StatusIn(BaseModel):
    status: str


class OrderEditIn(BaseModel):
    items: List[CartItemIn]


class CallIn(BaseModel):
    table_number: int
    kind: str


class RatingIn(BaseModel):
    order_id: str
    food: int
    service: int
    speed: int
    comment: str = ""


class SettingsIn(BaseModel):
    restaurant_name: Optional[str] = None
    logo: Optional[str] = None
    primary_color: Optional[str] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    tax_rate: Optional[float] = None
    service_charge: Optional[float] = None
    table_count: Optional[int] = None


# ---------------- settings ----------------
DEFAULT_SETTINGS = {
    "restaurant_name": "Warung Nusantara",
    "logo": "",
    "primary_color": "#C94A29",
    "currency": "IDR",
    "language": "id",
    "tax_rate": 11.0,
    "service_charge": 5.0,
    "table_count": 5,
}


async def get_settings_doc() -> dict:
    s = await db.settings.find_one({"key": "main"})
    if not s:
        doc = {"key": "main", **DEFAULT_SETTINGS}
        await db.settings.insert_one(doc)
        s = doc
    return {k: s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}


@api.get("/settings")
async def read_settings():
    return await get_settings_doc()


@api.put("/settings")
async def update_settings(body: SettingsIn, user: dict = Depends(require_owner)):
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.settings.update_one({"key": "main"}, {"$set": upd}, upsert=True)
    await audit(user, "settings.update", ", ".join(f"{k}={v}" for k, v in upd.items()))
    s = await get_settings_doc()
    await manager.broadcast("settings_updated", s)
    return s


# ---------------- auth routes ----------------
@api.post("/auth/login")
async def login(body: LoginIn):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Akun tidak aktif")
    u = clean(user)
    token = create_access_token(u["id"], u["email"], u["role"])
    await audit(u, "auth.login", f"{u['email']} logged in")
    return {"user": u, "token": token}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    await audit(user, "auth.logout", f"{user['email']} logged out")
    return {"ok": True}


# ---------------- staff ----------------
@api.get("/staff")
async def list_staff(user: dict = Depends(require_owner)):
    docs = await db.users.find().sort("created_at", 1).to_list(200)
    return [clean(d) for d in docs]


@api.post("/staff")
async def create_staff(body: StaffIn, user: dict = Depends(require_owner)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email sudah digunakan")
    doc = {"name": body.name, "email": email, "password_hash": hash_password(body.password),
           "role": body.role if body.role in ("cashier", "owner") else "cashier",
           "active": True, "created_at": now_iso()}
    r = await db.users.insert_one(doc)
    await audit(user, "staff.create", f"created {email}")
    return clean(await db.users.find_one({"_id": r.inserted_id}))


@api.put("/staff/{sid}")
async def update_staff(sid: str, body: StaffUpdate, user: dict = Depends(require_owner)):
    upd = {}
    if body.name is not None:
        upd["name"] = body.name
    if body.active is not None:
        upd["active"] = body.active
    if body.password:
        upd["password_hash"] = hash_password(body.password)
    await db.users.update_one({"_id": oid(sid)}, {"$set": upd})
    await audit(user, "staff.update", f"updated staff {sid}: {list(upd.keys())}")
    return clean(await db.users.find_one({"_id": oid(sid)}))


# ---------------- menu ----------------
@api.get("/menu")
async def list_menu(include_unavailable: bool = True):
    q = {} if include_unavailable else {"available": True}
    docs = await db.menu_items.find(q).sort("name", 1).to_list(500)
    return [clean(d) for d in docs]


@api.post("/menu")
async def create_menu(body: MenuItemIn, user: dict = Depends(require_owner)):
    doc = body.model_dump()
    doc["created_at"] = now_iso()
    r = await db.menu_items.insert_one(doc)
    await audit(user, "menu.create", f"created item {body.name}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": r.inserted_id}))


@api.put("/menu/{mid}")
async def update_menu(mid: str, body: MenuItemIn, user: dict = Depends(require_owner)):
    old = await db.menu_items.find_one({"_id": oid(mid)})
    if not old:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.menu_items.update_one({"_id": oid(mid)}, {"$set": body.model_dump()})
    if float(old.get("price", 0)) != float(body.price):
        await audit(user, "menu.price_change", f"{body.name}: {old.get('price')} -> {body.price}")
    else:
        await audit(user, "menu.update", f"updated item {body.name}")
    await manager.broadcast("menu_updated", {})
    return clean(await db.menu_items.find_one({"_id": oid(mid)}))


@api.delete("/menu/{mid}")
async def delete_menu(mid: str, user: dict = Depends(require_owner)):
    doc = await db.menu_items.find_one({"_id": oid(mid)})
    await db.menu_items.delete_one({"_id": oid(mid)})
    await audit(user, "menu.delete", f"deleted item {doc.get('name') if doc else mid}")
    await manager.broadcast("menu_updated", {})
    return {"ok": True}


# ---------------- orders ----------------
async def next_order_number() -> str:
    r = await db.counters.find_one_and_update({"_id": "order"}, {"$inc": {"seq": 1}},
                                              upsert=True, return_document=True)
    seq = r["seq"] if r else 1
    return f"INV-{datetime.now(timezone.utc).strftime('%y%m%d')}-{seq:04d}"


def compute_totals(items: List[dict], settings: dict) -> dict:
    subtotal = 0.0
    for it in items:
        line = it["unit_price"] + sum(float(o.get("price_delta", 0)) for o in it.get("options", []))
        subtotal += line * it["qty"]
    tax = round(subtotal * settings["tax_rate"] / 100, 2)
    service = round(subtotal * settings["service_charge"] / 100, 2)
    return {"subtotal": round(subtotal, 2), "tax": tax, "service": service,
            "total": round(subtotal + tax + service, 2)}


@api.post("/orders")
async def create_order(body: OrderIn):
    if not body.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    settings = await get_settings_doc()
    items = [i.model_dump() for i in body.items]
    totals = compute_totals(items, settings)
    doc = {
        "order_number": await next_order_number(),
        "table_number": body.table_number,
        "customer_name": body.customer_name,
        "items": items,
        **totals,
        "tax_rate": settings["tax_rate"], "service_rate": settings["service_charge"],
        "currency": settings["currency"],
        "status": "new", "paid": False,
        "accepted_by": None, "accepted_by_name": None,
        "modified_by_name": None,
        "history": [{"status": "new", "at": now_iso(), "by": "customer"}],
        "created_at": now_iso(),
    }
    r = await db.orders.insert_one(doc)
    out = clean(await db.orders.find_one({"_id": r.inserted_id}))
    await manager.broadcast("order_created", out)
    return out


@api.get("/orders/{order_id}")
async def get_order(order_id: str):
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    return clean(o)


@api.get("/orders")
async def list_orders(scope: str = "all", user: dict = Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if scope == "mine" or user["role"] == "cashier":
        q = {"$or": [{"status": "new"}, {"accepted_by": user["id"]}]}
    docs = await db.orders.find(q).sort("created_at", -1).to_list(300)
    return [clean(d) for d in docs]


@api.get("/tables/{table_number}/orders")
async def table_orders(table_number: int):
    docs = await db.orders.find({"table_number": table_number}).sort("created_at", -1).to_list(30)
    return [clean(d) for d in docs]


def can_modify(order: dict, user: dict) -> bool:
    return user["role"] == "owner" or order.get("accepted_by") == user["id"]


@api.post("/orders/{order_id}/accept")
async def accept_order(order_id: str, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if o["status"] != "new":
        raise HTTPException(status_code=400, detail="Pesanan sudah diterima kasir lain")
    upd = {"status": "accepted", "accepted_by": user["id"], "accepted_by_name": user["name"],
           "accepted_at": now_iso(), "modified_by_name": user["name"], "edit_until":
           (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()}
    await db.orders.update_one({"_id": oid(order_id)}, {
        "$set": upd,
        "$push": {"history": {"status": "accepted", "at": now_iso(), "by": user["name"]}}})
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.accept", f"accepted {o['order_number']}")
    await manager.broadcast("order_updated", out)
    return out


@api.post("/orders/{order_id}/status")
async def set_status(order_id: str, body: StatusIn, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_modify(o, user):
        raise HTTPException(status_code=403, detail="Hanya kasir penanggung jawab yang bisa mengubah")
    cur, nxt = o["status"], body.status
    if nxt not in STATUS_FLOW:
        raise HTTPException(status_code=400, detail="Status tidak valid")
    if STATUS_FLOW.index(nxt) != STATUS_FLOW.index(cur) + 1:
        raise HTTPException(status_code=400, detail=f"Alur status harus berurutan ({cur} -> berikutnya)")
    upd = {"status": nxt, "modified_by_name": user["name"]}
    if nxt == "closed":
        upd["paid"] = True
        upd["closed_at"] = now_iso()
    await db.orders.update_one({"_id": oid(order_id)}, {
        "$set": upd, "$push": {"history": {"status": nxt, "at": now_iso(), "by": user["name"]}}})
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.status", f"{o['order_number']}: {cur} -> {nxt}")
    await manager.broadcast("order_updated", out)
    return out


@api.put("/orders/{order_id}/items")
async def edit_order(order_id: str, body: OrderEditIn, user: dict = Depends(get_current_user)):
    o = await db.orders.find_one({"_id": oid(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    if not can_modify(o, user):
        raise HTTPException(status_code=403, detail="Hanya kasir penanggung jawab yang bisa mengubah")
    if user["role"] != "owner":
        limit = o.get("edit_until")
        if not limit or datetime.fromisoformat(limit) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Jendela edit 60 detik telah berakhir")
    settings = await get_settings_doc()
    items = [i.model_dump() for i in body.items]
    totals = compute_totals(items, settings)
    await db.orders.update_one({"_id": oid(order_id)}, {"$set": {
        "items": items, **totals, "modified_by_name": user["name"]}})
    out = clean(await db.orders.find_one({"_id": oid(order_id)}))
    await audit(user, "order.edit", f"edited items of {o['order_number']}")
    await manager.broadcast("order_updated", out)
    return out


# ---------------- calls ----------------
@api.post("/calls")
async def create_call(body: CallIn):
    doc = {"table_number": body.table_number, "kind": body.kind, "status": "open",
           "created_at": now_iso(), "handled_by_name": None}
    r = await db.calls.insert_one(doc)
    out = clean(await db.calls.find_one({"_id": r.inserted_id}))
    await manager.broadcast("call_created", out)
    return out


@api.get("/calls")
async def list_calls(user: dict = Depends(get_current_user)):
    docs = await db.calls.find().sort("created_at", -1).to_list(100)
    return [clean(d) for d in docs]


@api.post("/calls/{cid}/resolve")
async def resolve_call(cid: str, user: dict = Depends(get_current_user)):
    await db.calls.update_one({"_id": oid(cid)}, {"$set": {
        "status": "resolved", "handled_by_name": user["name"], "resolved_at": now_iso()}})
    out = clean(await db.calls.find_one({"_id": oid(cid)}))
    await manager.broadcast("call_updated", out)
    return out


# ---------------- ratings ----------------
@api.post("/ratings")
async def create_rating(body: RatingIn):
    doc = body.model_dump()
    doc["created_at"] = now_iso()
    await db.ratings.insert_one(doc)
    return {"ok": True}


@api.get("/ratings")
async def list_ratings(user: dict = Depends(require_owner)):
    docs = await db.ratings.find().sort("created_at", -1).to_list(200)
    return [clean(d) for d in docs]


# ---------------- shifts ----------------
@api.get("/shifts/current")
async def current_shift(user: dict = Depends(get_current_user)):
    s = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    return clean(s)


@api.post("/shifts/start")
async def start_shift(user: dict = Depends(get_current_user)):
    ex = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if ex:
        return clean(ex)
    doc = {"user_id": user["id"], "user_name": user["name"], "status": "open",
           "started_at": now_iso()}
    r = await db.shifts.insert_one(doc)
    await audit(user, "shift.start", f"{user['name']} started shift")
    return clean(await db.shifts.find_one({"_id": r.inserted_id}))


@api.post("/shifts/end")
async def end_shift(user: dict = Depends(get_current_user)):
    s = await db.shifts.find_one({"user_id": user["id"], "status": "open"})
    if not s:
        raise HTTPException(status_code=400, detail="Tidak ada shift aktif")
    orders = await db.orders.find({"accepted_by": user["id"],
                                   "created_at": {"$gte": s["started_at"]}}).to_list(1000)
    total_cash = sum(o["total"] for o in orders if o.get("paid"))
    await db.shifts.update_one({"_id": s["_id"]}, {"$set": {
        "status": "closed", "ended_at": now_iso(),
        "orders_count": len(orders), "total_cash": round(total_cash, 2)}})
    await audit(user, "shift.end", f"{user['name']} ended shift, {len(orders)} orders")
    return clean(await db.shifts.find_one({"_id": s["_id"]}))


@api.get("/shifts")
async def list_shifts(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "owner" else {"user_id": user["id"]}
    docs = await db.shifts.find(q).sort("started_at", -1).to_list(100)
    return [clean(d) for d in docs]


# ---------------- reports / audit ----------------
@api.get("/reports")
async def reports(period: str = "day", user: dict = Depends(require_owner)):
    days = {"day": 1, "week": 7, "month": 30}.get(period, 1)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    orders = await db.orders.find({"created_at": {"$gte": since}}).to_list(2000)
    paid = [o for o in orders if o.get("paid")]
    revenue = sum(o["total"] for o in paid)
    item_counts: Dict[str, int] = {}
    hours: Dict[str, int] = {}
    for o in orders:
        for it in o["items"]:
            item_counts[it["name"]] = item_counts.get(it["name"], 0) + it["qty"]
        h = datetime.fromisoformat(o["created_at"]).strftime("%H:00")
        hours[h] = hours.get(h, 0) + 1
    ranked = sorted(item_counts.items(), key=lambda x: -x[1])
    return {
        "period": period,
        "orders_count": len(orders),
        "paid_count": len(paid),
        "revenue": round(revenue, 2),
        "avg_order_value": round(revenue / len(paid), 2) if paid else 0,
        "best_sellers": [{"name": n, "qty": q} for n, q in ranked[:5]],
        "worst_sellers": [{"name": n, "qty": q} for n, q in ranked[-5:][::-1]],
        "busiest_hours": [{"hour": h, "orders": c} for h, c in sorted(hours.items())],
    }


@api.get("/audit")
async def audit_list(user: dict = Depends(require_owner)):
    docs = await db.audit_logs.find().sort("created_at", -1).to_list(200)
    return [clean(d) for d in docs]


# ---------------- seed ----------------
MENU_SEED = [
    ("Nasi Goreng Spesial", "Nasi goreng dengan ayam, telur mata sapi, dan acar", "Makanan Utama", 45000, None,
     "https://images.unsplash.com/photo-1512058564366-18510be2db19?w=800&q=70"),
    ("Ayam Bakar Madu", "Ayam kampung bakar bumbu madu, sambal terasi", "Makanan Utama", 55000, 49000,
     "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=800&q=70"),
    ("Rendang Daging", "Rendang sapi khas Padang dimasak 6 jam", "Makanan Utama", 65000, None,
     "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=800&q=70"),
    ("Mie Goreng Jawa", "Mie goreng dengan sayuran segar dan bakso", "Makanan Utama", 38000, None,
     "https://images.unsplash.com/photo-1585032226651-759b368d7246?w=800&q=70"),
    ("Sate Ayam Madura", "10 tusuk sate ayam saus kacang", "Makanan Utama", 42000, None,
     "https://images.unsplash.com/photo-1529563021893-cc83c992d75d?w=800&q=70"),
    ("Gado-Gado", "Sayuran segar dengan saus kacang dan kerupuk", "Pembuka", 32000, None,
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=800&q=70"),
    ("Lumpia Semarang", "Lumpia isi rebung dan ayam, 4 potong", "Pembuka", 28000, 24000,
     "https://images.unsplash.com/photo-1625938144755-652e08e359b7?w=800&q=70"),
    ("Tahu Crispy", "Tahu goreng crispy saus sambal manis", "Pembuka", 22000, None,
     "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=70"),
    ("Es Teh Manis", "Teh tubruk dingin dengan gula batu", "Minuman", 12000, None,
     "https://images.unsplash.com/photo-1499638673689-79a0b5115d87?w=800&q=70"),
    ("Kopi Susu Gula Aren", "Espresso, susu segar, gula aren", "Minuman", 25000, 22000,
     "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=800&q=70"),
    ("Jus Alpukat", "Jus alpukat dengan susu kental manis", "Minuman", 28000, None,
     "https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?w=800&q=70"),
    ("Es Jeruk Peras", "Jeruk peras segar dengan es batu", "Minuman", 15000, None,
     "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=800&q=70"),
    ("Es Cendol Durian", "Cendol, santan, gula merah, durian", "Penutup", 30000, None,
     "https://images.unsplash.com/photo-1488900128323-21503983a07e?w=800&q=70"),
    ("Pisang Goreng Keju", "Pisang goreng crispy topping keju", "Penutup", 24000, None,
     "https://images.unsplash.com/photo-1541592106381-b31e9677c0e5?w=800&q=70"),
    ("Klepon", "Kue klepon isi gula merah, 6 buah", "Penutup", 18000, None,
     "https://images.unsplash.com/photo-1519676867240-f03562e64548?w=800&q=70"),
]

SPICE = {"name": "Tingkat Kepedasan", "required": True, "choices": [
    {"label": "Tidak Pedas", "price_delta": 0}, {"label": "Sedang", "price_delta": 0},
    {"label": "Pedas", "price_delta": 0}, {"label": "Extra Pedas", "price_delta": 2000}]}
SIZE = {"name": "Ukuran", "required": True, "choices": [
    {"label": "Regular", "price_delta": 0}, {"label": "Large", "price_delta": 8000}]}
SUGAR = {"name": "Level Gula", "required": True, "choices": [
    {"label": "Tanpa Gula", "price_delta": 0}, {"label": "Sedikit", "price_delta": 0},
    {"label": "Normal", "price_delta": 0}]}
EXTRAS = {"name": "Tambahan", "required": False, "choices": [
    {"label": "Extra Nasi", "price_delta": 8000}, {"label": "Telur Ceplok", "price_delta": 7000},
    {"label": "Kerupuk", "price_delta": 5000}]}


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await get_settings_doc()

    accounts = [
        (os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"], "Pak Budi (Owner)", "owner"),
        ("kasir1@restos.id", "kasir123", "Siti Kasir", "cashier"),
        ("kasir2@restos.id", "kasir123", "Andi Kasir", "cashier"),
    ]
    for email, pwd, name, role in accounts:
        ex = await db.users.find_one({"email": email})
        if not ex:
            await db.users.insert_one({"email": email, "password_hash": hash_password(pwd),
                                       "name": name, "role": role, "active": True,
                                       "created_at": now_iso()})
        elif not verify_password(pwd, ex["password_hash"]):
            await db.users.update_one({"_id": ex["_id"]},
                                      {"$set": {"password_hash": hash_password(pwd)}})

    if await db.menu_items.count_documents({}) == 0:
        docs = []
        for name, desc, cat, price, disc, img in MENU_SEED:
            if cat == "Minuman":
                opts = [SIZE, SUGAR]
            elif cat == "Penutup":
                opts = [SIZE]
            else:
                opts = [SPICE, EXTRAS]
            docs.append({"name": name, "description": desc, "category": cat, "price": price,
                         "discount_price": disc, "image": img, "available": True,
                         "options": opts, "created_at": now_iso()})
        await db.menu_items.insert_many(docs)
    logger.info("REST-OS startup complete")


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
