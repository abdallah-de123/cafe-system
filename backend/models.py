"""Pydantic request models for all routers (what clients are allowed to send)."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class LoginIn(BaseModel):
    email: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class OptionChoice(BaseModel):
    label: str
    label_en: str = ""
    label_ar: str = ""
    price_delta: float = Field(0, ge=0)


class OptionGroup(BaseModel):
    name: str
    name_en: str = ""
    name_ar: str = ""
    required: bool = False
    choices: List[OptionChoice] = []


class MenuConsume(BaseModel):
    """One inventory ingredient used for each sold unit of a menu item."""
    inventory_item_id: str = Field(min_length=24, max_length=24)
    qty_per_unit: float = Field(gt=0, le=1000000)


class MenuItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    name_en: str = ""
    name_ar: str = ""
    description_en: str = ""
    description_ar: str = ""
    image: str = ""
    image_thumbnail: str = Field("", max_length=2000)
    price: float = Field(ge=0)
    discount_price: Optional[float] = Field(None, ge=0)
    category: str = Field(min_length=1, max_length=60)
    available: bool = True
    options: List[OptionGroup] = []
    consumes: List[MenuConsume] = Field(default_factory=list, max_length=50)


class AvailabilityIn(BaseModel):
    available: bool


class ImageDeleteIn(BaseModel):
    """Only an owner or super admin may discard an unused generated image URL."""
    image: str = Field(min_length=1, max_length=2000)


class InventoryItemCreate(BaseModel):
    """Create a tracked stock item, optionally with a starting amount."""
    name: str = Field(min_length=1, max_length=120)
    name_en: str = Field("", max_length=120)
    name_ar: str = Field("", max_length=120)
    unit: str = Field(min_length=1, max_length=40)
    initial_quantity: float = Field(0, ge=0, le=1000000000)
    low_stock_threshold: Optional[float] = Field(None, ge=0, le=1000000000)
    cost_per_unit: Optional[float] = Field(None, ge=0, le=1000000000)


class InventoryItemUpdate(BaseModel):
    """Update inventory details; quantity changes must go through a movement."""
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    name_en: Optional[str] = Field(None, max_length=120)
    name_ar: Optional[str] = Field(None, max_length=120)
    unit: Optional[str] = Field(None, min_length=1, max_length=40)
    low_stock_threshold: Optional[float] = Field(None, ge=0, le=1000000000)
    cost_per_unit: Optional[float] = Field(None, ge=0, le=1000000000)
    active: Optional[bool] = None


class InventoryMovementIn(BaseModel):
    """Manual stock movement. Adjustment accepts a signed quantity delta."""
    kind: Literal["restock", "adjustment", "waste"]
    quantity: float = Field(ge=-1000000000, le=1000000000)
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("quantity")
    @classmethod
    def _movement_quantity(cls, value, info):
        if value == 0 or (info.data.get("kind") in {"restock", "waste"} and value < 0):
            raise ValueError("quantity must be positive")
        return value

    @field_validator("reason")
    @classmethod
    def _movement_reason(cls, value):
        if not value.strip():
            raise ValueError("reason is required")
        return value.strip()


class CancelOrderIn(BaseModel):
    """Required explanation and actor metadata for cancelling an order."""
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def _reason_text(cls, value):
        if not value.strip():
            raise ValueError("reason is required")
        return value.strip()


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str
    password: str
    role: Literal["super_admin", "owner", "cashier"] = "cashier"


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    active: Optional[bool] = None
    password: Optional[str] = None
    role: Optional[Literal["super_admin", "owner", "cashier"]] = None


class ChosenOption(BaseModel):
    """A customer's pick: which option group and which choice label. Price comes from the server."""
    group: str = ""
    label: str
    # Ignored by the server (kept so older clients can still send them).
    label_en: Optional[str] = None
    label_ar: Optional[str] = None
    price_delta: Optional[float] = None


class CartItemIn(BaseModel):
    """What the customer sends per line. Name and unit_price are ignored; the server prices it."""
    menu_item_id: str
    qty: int = Field(1, ge=1, le=99)
    options: List[ChosenOption] = []
    note: str = Field("", max_length=200)
    name: Optional[str] = None
    unit_price: Optional[float] = None


class OrderIn(BaseModel):
    table_number: int
    items: List[CartItemIn]
    customer_name: str = Field("", max_length=80)


class OrderEditIn(BaseModel):
    items: List[CartItemIn]


class StatusIn(BaseModel):
    status: str
    payment_method: Optional[Literal["cash", "card", "qris", "other"]] = None
    amount_received: Optional[float] = Field(None, ge=0)


class ShiftStartIn(BaseModel):
    """Cash in the till before the cashier starts a shift."""
    opening_cash: float = Field(0, ge=0, le=1000000000000)


class ShiftEndIn(BaseModel):
    """Physical cash count entered before ending the cashier's shift."""
    counted_cash: float = Field(ge=0, le=1000000000000)


class BillingTopUpIn(BaseModel):
    amount: float = Field(gt=0, le=100000000000000)
    note: str = Field("", max_length=300)


class BillingMonthPaymentIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    note: str = Field("", max_length=300)
    paid: bool = True


class OrderRefundIn(BaseModel):
    amount: Optional[float] = Field(None, gt=0, le=1000000000000)
    reason: str = Field(min_length=1, max_length=300)

    @field_validator("reason")
    @classmethod
    def _refund_reason(cls, value):
        if not value.strip():
            raise ValueError("reason is required")
        return value.strip()


class MyOrdersIn(BaseModel):
    """Customer asks for their own orders by proving the order tokens they hold."""
    tokens: List[str] = Field(default_factory=list, max_length=50)


class CallIn(BaseModel):
    table_number: int
    kind: Literal["help", "bill", "clean"]


class RatingIn(BaseModel):
    order_id: str
    token: str = ""
    food: int = Field(ge=1, le=5)
    service: int = Field(ge=1, le=5)
    speed: int = Field(ge=1, le=5)
    comment: str = Field("", max_length=300)
