"""Billing totals and business-calendar rules for Phase 4."""
from datetime import datetime, timezone

from core.billing import invoice_amounts
from core.reporting import business_range
from core.settings import DEFAULT_ADMIN_SETTINGS


def test_system_fee_default_is_one_thousand():
    assert DEFAULT_ADMIN_SETTINGS["fee_per_invoice"] == 1000


def test_system_fee_uses_restaurant_currency_and_tax_applies_to_fee():
    values = invoice_amounts(
        {"total": 110, "currency": "SAR"},
        {"currency": "SAR", "tax_rate": 10, "tax_enabled": True},
        {"billing_enabled": True, "fee_per_invoice": 10},
    )
    assert values == {"restaurant_total": 110, "system_fee": 10, "system_fee_tax": 1, "invoice_total": 121}


def test_billing_disabled_leaves_restaurant_total_unchanged():
    values = invoice_amounts(
        {"total": 100}, {"tax_rate": 10, "tax_enabled": True},
        {"billing_enabled": False, "fee_per_invoice": 10},
    )
    assert values["invoice_total"] == 100
    assert values["system_fee"] == values["system_fee_tax"] == 0


def test_custom_report_range_uses_local_business_day_boundary():
    start, end, first, last = business_range(
        {"timezone": "Asia/Riyadh", "business_day_start": "06:00"},
        start_date="2026-10-01", end_date="2026-10-02",
    )
    assert (first, last) == ("2026-10-01", "2026-10-02")
    assert start == datetime(2026, 10, 1, 3, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 3, 3, tzinfo=timezone.utc)
