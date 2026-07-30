from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.booking_datetime import (
    BookingDateTimeError,
    normalize_text,
    parse_booking_date,
)


MONTH_NAMES = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}


def _format_booking_date(value: datetime.date) -> str:
    return (
        f"{value.day} "
        f"{MONTH_NAMES[value.month]} "
        f"{value.year}"
    )


def resolve_relative_reference(
    *,
    message: str,
    context: dict[str, Any] | None,
    timezone_name: str = "Africa/Algiers",
    now: datetime | None = None,
) -> str:
    """Resout les references conversationnelles relatives."""
    normalized_message = normalize_text(message)

    if normalized_message != "le lendemain":
        return message

    if not context:
        return message

    previous_date_text = context.get("requested_date_text")

    if not previous_date_text:
        return message

    timezone = ZoneInfo(timezone_name)
    current = now.astimezone(timezone) if now else datetime.now(timezone)

    try:
        previous_date = parse_booking_date(
            date_text=str(previous_date_text),
            current=current,
        )
    except BookingDateTimeError:
        return message

    resolved_date = previous_date + timedelta(days=1)

    return _format_booking_date(resolved_date)
