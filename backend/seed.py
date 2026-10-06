"""Seeding and one-time migrations.

- Super admin: created once from ADMIN_EMAIL / ADMIN_PASSWORD env vars, never overwritten.
- Demo menu: inserted only when SEED_DEMO=true AND the menu is empty ($setOnInsert only).
- Demo accounts from early versions are removed once and never recreated.
"""
import logging
import os

from core.db import db, now_iso
from core.security import hash_password, DEMO_EMAILS

logger = logging.getLogger("restos")

MENU_SEED = [
    ("Nasi Goreng Spesial", "Nasi goreng dengan ayam, telur mata sapi, dan acar", "Makanan Utama", 45000, None,
     "https://images.unsplash.com/photo-1512058564366-18510be2db19?w=800&q=70",
     "Special Fried Rice", "Fried rice with chicken, sunny-side egg and pickles",
     "أرز مقلي خاص", "أرز مقلي مع الدجاج والبيض والمخللات"),
    ("Ayam Bakar Madu", "Ayam kampung bakar bumbu madu, sambal terasi", "Makanan Utama", 55000, 49000,
     "https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?w=800&q=70",
     "Honey Grilled Chicken", "Free-range grilled chicken with honey glaze and chili paste",
     "دجاج مشوي بالعسل", "دجاج بلدي مشوي بصلصة العسل مع الصلصة الحارة"),
    ("Rendang Daging", "Rendang sapi khas Padang dimasak 6 jam", "Makanan Utama", 65000, None,
     "https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?w=800&q=70",
     "Beef Rendang", "Padang-style slow-cooked beef rendang, 6 hours",
     "رندانغ لحم", "لحم بقري مطهو ببطء على طريقة بادانغ لمدة 6 ساعات"),
    ("Mie Goreng Jawa", "Mie goreng dengan sayuran segar dan bakso", "Makanan Utama", 38000, None,
     "https://images.unsplash.com/photo-1585032226651-759b368d7246?w=800&q=70",
     "Javanese Fried Noodles", "Fried noodles with fresh vegetables and meatballs",
     "نودلز جاوي مقلي", "نودلز مقلي مع الخضار الطازجة وكرات اللحم"),
    ("Sate Ayam Madura", "10 tusuk sate ayam saus kacang", "Makanan Utama", 42000, None,
     "https://images.unsplash.com/photo-1529563021893-cc83c992d75d?w=800&q=70",
     "Chicken Satay", "10 chicken skewers with peanut sauce",
     "ساتاي دجاج", "10 أسياخ دجاج مع صلصة الفول السوداني"),
    ("Gado-Gado", "Sayuran segar dengan saus kacang dan kerupuk", "Pembuka", 32000, None,
     "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=800&q=70",
     "Gado-Gado Salad", "Fresh vegetables with peanut sauce and crackers",
     "سلطة غادو غادو", "خضار طازجة مع صلصة الفول السوداني والمقرمشات"),
    ("Lumpia Semarang", "Lumpia isi rebung dan ayam, 4 potong", "Pembuka", 28000, 24000,
     "https://images.unsplash.com/photo-1625938144755-652e08e359b7?w=800&q=70",
     "Semarang Spring Rolls", "Bamboo shoot and chicken spring rolls, 4 pcs",
     "لفائف سيمارانغ", "لفائف محشوة بالدجاج وبراعم البامبو، 4 قطع"),
    ("Tahu Crispy", "Tahu goreng crispy saus sambal manis", "Pembuka", 22000, None,
     "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=70",
     "Crispy Tofu", "Crispy fried tofu with sweet chili sauce",
     "توفو مقرمش", "توفو مقلي مقرمش مع صلصة الفلفل الحلو"),
    ("Es Teh Manis", "Teh tubruk dingin dengan gula batu", "Minuman", 12000, None,
     "https://images.unsplash.com/photo-1499638673689-79a0b5115d87?w=800&q=70",
     "Iced Sweet Tea", "Chilled black tea with rock sugar",
     "شاي مثلج محلى", "شاي أسود مثلج مع سكر النبات"),
    ("Kopi Susu Gula Aren", "Espresso, susu segar, gula aren", "Minuman", 25000, 22000,
     "https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=800&q=70",
     "Palm Sugar Latte", "Espresso, fresh milk and palm sugar",
     "لاتيه بسكر النخيل", "إسبريسو مع الحليب الطازج وسكر النخيل"),
    ("Jus Alpukat", "Jus alpukat dengan susu kental manis", "Minuman", 28000, None,
     "https://images.unsplash.com/photo-1623065422902-30a2d299bbe4?w=800&q=70",
     "Avocado Juice", "Avocado blended with condensed milk",
     "عصير أفوكادو", "أفوكادو مخفوق مع الحليب المكثف"),
    ("Es Jeruk Peras", "Jeruk peras segar dengan es batu", "Minuman", 15000, None,
     "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=800&q=70",
     "Iced Orange Juice", "Freshly squeezed orange juice over ice",
     "عصير برتقال مثلج", "عصير برتقال طازج مع الثلج"),
    ("Es Cendol Durian", "Cendol, santan, gula merah, durian", "Penutup", 30000, None,
     "https://images.unsplash.com/photo-1488900128323-21503983a07e?w=800&q=70",
     "Durian Cendol", "Cendol with coconut milk, palm sugar and durian",
     "تشندول بالدوريان", "تشندول مع حليب جوز الهند وسكر النخيل والدوريان"),
    ("Pisang Goreng Keju", "Pisang goreng crispy topping keju", "Penutup", 24000, None,
     "https://images.unsplash.com/photo-1541592106381-b31e9677c0e5?w=800&q=70",
     "Cheese Banana Fritters", "Crispy fried banana topped with cheese",
     "موز مقلي بالجبن", "موز مقلي مقرمش مع الجبن"),
    ("Klepon", "Kue klepon isi gula merah, 6 buah", "Penutup", 18000, None,
     "https://images.unsplash.com/photo-1519676867240-f03562e64548?w=800&q=70",
     "Klepon Rice Cakes", "Rice cakes filled with palm sugar, 6 pcs",
     "كليبون", "كرات أرز محشوة بسكر النخيل، 6 حبات"),
]

CATEGORY_I18N = {
    "Makanan Utama": {"en": "Main Course", "ar": "الأطباق الرئيسية"},
    "Pembuka": {"en": "Starters", "ar": "المقبلات"},
    "Minuman": {"en": "Drinks", "ar": "المشروبات"},
    "Penutup": {"en": "Desserts", "ar": "الحلويات"},
}

SPICE = {"name": "Tingkat Kepedasan", "name_en": "Spice Level", "name_ar": "مستوى الحرارة",
         "required": True, "choices": [
    {"label": "Tidak Pedas", "label_en": "Not Spicy", "label_ar": "غير حار", "price_delta": 0},
    {"label": "Sedang", "label_en": "Medium", "label_ar": "متوسط", "price_delta": 0},
    {"label": "Pedas", "label_en": "Spicy", "label_ar": "حار", "price_delta": 0},
    {"label": "Extra Pedas", "label_en": "Extra Spicy", "label_ar": "حار جداً", "price_delta": 2000}]}
SIZE = {"name": "Ukuran", "name_en": "Size", "name_ar": "الحجم", "required": True, "choices": [
    {"label": "Regular", "label_en": "Regular", "label_ar": "عادي", "price_delta": 0},
    {"label": "Large", "label_en": "Large", "label_ar": "كبير", "price_delta": 8000}]}
SUGAR = {"name": "Level Gula", "name_en": "Sugar Level", "name_ar": "مستوى السكر",
         "required": True, "choices": [
    {"label": "Tanpa Gula", "label_en": "No Sugar", "label_ar": "بدون سكر", "price_delta": 0},
    {"label": "Sedikit", "label_en": "Less Sugar", "label_ar": "سكر قليل", "price_delta": 0},
    {"label": "Normal", "label_en": "Normal", "label_ar": "عادي", "price_delta": 0}]}
EXTRAS = {"name": "Tambahan", "name_en": "Add-ons", "name_ar": "الإضافات", "required": False, "choices": [
    {"label": "Extra Nasi", "label_en": "Extra Rice", "label_ar": "أرز إضافي", "price_delta": 8000},
    {"label": "Telur Ceplok", "label_en": "Fried Egg", "label_ar": "بيضة مقلية", "price_delta": 7000},
    {"label": "Kerupuk", "label_en": "Crackers", "label_ar": "مقرمشات", "price_delta": 5000}]}


def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


async def seed_super_admin():
    """Create the first super admin from env, only if that email does not exist yet."""
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD") or ""
    if not email or not password:
        logger.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set: no super admin seeded")
        return
    if email in DEMO_EMAILS or "@" not in email or len(password) < 8:
        logger.warning("ADMIN_EMAIL is a demo/invalid address or ADMIN_PASSWORD too short: super admin NOT seeded")
        return
    if await db.users.find_one({"email": email}):
        return  # never touch an existing account (email or password)
    await db.users.insert_one({"email": email, "password_hash": hash_password(password),
                               "name": "Super Admin", "role": "super_admin", "active": True,
                               "token_version": 0, "deleted_at": None, "created_at": now_iso()})
    logger.info("Super admin created")


async def remove_demo_accounts():
    """One-time cleanup: delete the publicly known demo accounts. Runs once, recorded in `migrations`."""
    if await db.migrations.find_one({"_id": "remove_demo_accounts"}):
        return
    res = await db.users.delete_many({"email": {"$in": list(DEMO_EMAILS)}})
    await db.migrations.insert_one({"_id": "remove_demo_accounts", "deleted": res.deleted_count, "at": now_iso()})
    if res.deleted_count:
        logger.info("Removed %s demo accounts", res.deleted_count)


async def seed_demo_menu():
    """Insert the sample menu only when SEED_DEMO=true and there are no menu items at all."""
    if not _truthy(os.environ.get("SEED_DEMO", "")):
        return
    if await db.menu_items.count_documents({}) > 0:
        return
    for name, desc, cat, price, disc, img, name_en, desc_en, name_ar, desc_ar in MENU_SEED:
        opts = [SIZE, SUGAR] if cat == "Minuman" else [SIZE] if cat == "Penutup" else [SPICE, EXTRAS]
        doc = {"name": name, "description": desc, "category": cat, "price": price,
               "discount_price": disc, "image": img, "available": True,
               "name_en": name_en, "description_en": desc_en,
               "name_ar": name_ar, "description_ar": desc_ar, "options": opts}
        await db.menu_items.update_one({"name": name}, {"$setOnInsert": {**doc, "created_at": now_iso()}}, upsert=True)
    logger.info("Demo menu seeded")


async def migrate_users():
    """Make sure every existing user has the new fields (token_version, deleted_at)."""
    await db.users.update_many({"token_version": {"$exists": False}}, {"$set": {"token_version": 0}})
    await db.users.update_many({"deleted_at": {"$exists": False}}, {"$set": {"deleted_at": None}})
