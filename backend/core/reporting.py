"""Timezone-aware business-day ranges and database-side reporting helpers."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def business_range(settings: dict, period: str = "day", start_date: str | None = None,
                   end_date: str | None = None) -> tuple[datetime, datetime, str, str]:
    """Build an inclusive local-date range using the restaurant's business-day start."""
    zone = ZoneInfo(settings["timezone"])
    start_time = time.fromisoformat(settings.get("business_day_start", "00:00"))
    now = datetime.now(zone)
    business_date = now.date() if now.timetz().replace(tzinfo=None) >= start_time else now.date() - timedelta(days=1)

    if start_date or end_date:
        first = date.fromisoformat(start_date) if start_date else business_date
        last = date.fromisoformat(end_date) if end_date else first
        if last < first:
            raise ValueError("end_date must be on or after start_date")
    elif period == "day":
        first = last = business_date
    elif period == "week":
        first = business_date - timedelta(days=business_date.weekday())
        last = first + timedelta(days=6)
    elif period == "month":
        first = business_date.replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        last = next_month - timedelta(days=1)
    else:
        raise ValueError("period must be day, week, or month")

    local_start = datetime.combine(first, start_time, tzinfo=zone)
    local_end = datetime.combine(last + timedelta(days=1), start_time, tzinfo=zone)
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)
    return utc_start, utc_end, first.isoformat(), last.isoformat()
