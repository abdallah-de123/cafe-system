"""Pydantic request models for all routers (what clients are allowed to send)."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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


class MenuItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    name_en: str = ""
    name_ar: str = ""
    description_en: str = ""
    description_ar: str = ""
    image: str = ""
    price: float = Field(ge=0)
    discount_price: Optional[float] = Field(None, ge=0)
    category: str = Field(min_length=1, max_length=60)
    available: bool = True
    options: List[OptionGroup] = []


class AvailabilityIn(BaseModel):
    available: bool


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
