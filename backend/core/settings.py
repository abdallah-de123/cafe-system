"""Restaurant settings: defaults, validation, and read/write helpers.

Settings live in one Mongo document (`settings`, key="main"). Public keys are readable by
everyone (customers need currency, languages, etc.). Admin keys (`admin` sub-document) are
only visible to the super admin: license, feature flags, billing configuration.
"""
from typing import Dict, List, Literal, Optional
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

from core.db import db

LANG_CODES = ("id", "en", "ar")

# Defaults for every public setting. New features read these even before their UI ships.
DEFAULT_SETTINGS: Dict = {
    # General / restaurant info
    "restaurant_name": "Warung Nusantara",
    "logo": "",
    "primary_color": "#C94A29",
    "phone": "",
    "address": "",
    "opening_hours": "",
    "receipt_footer": "",
    "wifi_name": "",
    "wifi_password": "",
    # Time and language
    "timezone": "Asia/Jakarta",
    "business_day_start": "06:00",
    "business_day_end": "23:00",
    "language": "id",
    "enabled_languages": ["id", "en", "ar"],
    # Money
    "currency": "IDR",
    "tax_rate": 11.0,
    "tax_enabled": True,
    "service_charge": 5.0,
    "service_enabled": True,
    "prices_include_tax": False,
    "payment_methods": {"cash": True, "card": True, "qris": True, "other": False},
    "rounding": "none",
    # Orders
    "table_count": 5,
    "edit_window_seconds": 60,
    "require_customer_name": False,
    "require_table_number": True,
    "accepting_orders": True,
    "new_order_sound": True,
    # Inventory (takes effect in Phase 3)
    "default_low_stock_threshold": 20,
    "auto_hide_out_of_stock": True,
    "alert_in_app": True,
    # Security
    "session_hours": 24,
    "min_password_length": 8,
}

# Super-admin-only settings (hidden from owners). Billing takes effect in Phase 4.
DEFAULT_ADMIN_SETTINGS: Dict = {
    "license_expires_at": None,
    "feature_flags": {"seed_demo": False},
    "billing_enabled": False,
    "billing_mode": "monthly",
    "fee_per_invoice": 2500,
    "low_balance_warning": 50000,
    "zero_balance_behavior": "warn_grace",
    "grace_invoices": 20,
    "reversal_refunds_fee": False,
}


def _hhmm(v: str) -> str:
    """Validate a 'HH:MM' time string."""
    parts = v.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("time must be HH:MM")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("time out of range")
    return f"{h:02d}:{m:02d}"


class SettingsIn(BaseModel):
    """Partial update of public settings. Every field is optional; each has a sane range."""
    restaurant_name: Optional[str] = Field(None, min_length=1, max_length=120)
    logo: Optional[str] = Field(None, max_length=2000)
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    phone: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = Field(None, max_length=300)
    opening_hours: Optional[str] = Field(None, max_length=200)
    receipt_footer: Optional[str] = Field(None, max_length=300)
    wifi_name: Optional[str] = Field(None, max_length=60)
    wifi_password: Optional[str] = Field(None, max_length=60)
    timezone: Optional[str] = None
    business_day_start: Optional[str] = None
    business_day_end: Optional[str] = None
    language: Optional[Literal["id", "en", "ar"]] = None
    enabled_languages: Optional[List[Literal["id", "en", "ar"]]] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    tax_rate: Optional[float] = Field(None, ge=0, le=100)
    tax_enabled: Optional[bool] = None
    service_charge: Optional[float] = Field(None, ge=0, le=100)
    service_enabled: Optional[bool] = None
    prices_include_tax: Optional[bool] = None
    payment_methods: Optional[Dict[Literal["cash", "card", "qris", "other"], bool]] = None
    rounding: Optional[Literal["none", "100", "500"]] = None
    table_count: Optional[int] = Field(None, ge=1, le=500)
    edit_window_seconds: Optional[int] = Field(None, ge=0, le=3600)
    require_customer_name: Optional[bool] = None
    require_table_number: Optional[bool] = None
    accepting_orders: Optional[bool] = None
    new_order_sound: Optional[bool] = None
    default_low_stock_threshold: Optional[int] = Field(None, ge=0, le=100000)
    auto_hide_out_of_stock: Optional[bool] = None
    alert_in_app: Optional[bool] = None
    session_hours: Optional[int] = Field(None, ge=1, le=720)
    min_password_length: Optional[int] = Field(None, ge=6, le=64)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        if v is not None and v not in available_timezones():
            raise ValueError("unknown timezone")
        return v

    @field_validator("business_day_start", "business_day_end")
    @classmethod
    def _times(cls, v):
        return None if v is None else _hhmm(v)

    @field_validator("enabled_languages")
    @classmethod
    def _langs(cls, v):
        if v is not None and len(v) == 0:
            raise ValueError("at least one language must be enabled")
        return list(dict.fromkeys(v)) if v else v

    @field_validator("currency")
    @classmethod
    def _cur(cls, v):
        return v.upper() if v else v


class AdminSettingsIn(BaseModel):
    """Partial update of super-admin-only settings."""
    license_expires_at: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None
    billing_enabled: Optional[bool] = None
    billing_mode: Optional[Literal["monthly", "prepaid"]] = None
    fee_per_invoice: Optional[float] = Field(None, ge=0)
    low_balance_warning: Optional[float] = Field(None, ge=0)
    zero_balance_behavior: Optional[Literal["warn", "warn_grace", "block"]] = None
    grace_invoices: Optional[int] = Field(None, ge=0, le=10000)
    reversal_refunds_fee: Optional[bool] = None


async def get_settings_doc() -> dict:
    """Return public settings merged over defaults (creates the document on first use)."""
    s = await db.settings.find_one({"key": "main"})
    if not s:
        s = {"key": "main", **DEFAULT_SETTINGS, "admin": dict(DEFAULT_ADMIN_SETTINGS)}
        await db.settings.insert_one(s)
    out = {k: s.get(k, v) for k, v in DEFAULT_SETTINGS.items()}
    # The default language must always be one of the enabled languages.
    if out["language"] not in out["enabled_languages"]:
        out["language"] = out["enabled_languages"][0]
    return out


async def get_admin_settings() -> dict:
    """Return super-admin settings merged over defaults."""
    s = await db.settings.find_one({"key": "main"}) or {}
    a = s.get("admin") or {}
    return {k: a.get(k, v) for k, v in DEFAULT_ADMIN_SETTINGS.items()}
