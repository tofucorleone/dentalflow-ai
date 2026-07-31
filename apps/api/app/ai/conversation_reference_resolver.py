from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.booking_datetime import (
    BookingDateTimeError,
    normalize_text,
    parse_booking_date,
)


NUMBER_WORDS = {
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
}


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


def _parse_relative_time_offset(
    normalized_message: str,
) -> timedelta | None:
    match = re.fullmatch(
        r"(?P<amount>\d+|un|une|deux|trois)\s+"
        r"(?P<unit>heures?|minutes?)\s+plus\s+"
        r"(?P<direction>tard|tot)",
        normalized_message,
    )

    if match is not None:
        direction = match.group("direction")
    else:
        match = re.fullmatch(
            r"dans\s+"
            r"(?P<amount>\d+|un|une|deux|trois)\s+"
            r"(?P<unit>heures?|minutes?)",
            normalized_message,
        )

        if match is None:
            return None

        direction = "tard"

    raw_amount = match.group("amount")

    if raw_amount.isdigit():
        amount = int(raw_amount)
    else:
        amount = NUMBER_WORDS[raw_amount]

    unit = match.group("unit")
    signed_amount = amount if direction == "tard" else -amount

    if unit.startswith("heure"):
        return timedelta(hours=signed_amount)

    return timedelta(minutes=signed_amount)


def resolve_relative_reference(
    *,
    message: str,
    context: dict[str, Any] | None,
    timezone_name: str = "Africa/Algiers",
    now: datetime | None = None,
) -> str:
    """Resout les references conversationnelles relatives."""
    normalized_message = normalize_text(message)
    relative_time_offset = _parse_relative_time_offset(
        normalized_message,
    )

    if relative_time_offset is not None:
        if not context:
            return message

        previous_start_at = context.get("previous_start_at")

        if not previous_start_at:
            return message

        try:
            previous_start = datetime.fromisoformat(
                str(previous_start_at),
            )
        except ValueError:
            return message

        timezone = ZoneInfo(timezone_name)
        local_previous_start = previous_start.astimezone(timezone)
        resolved_start = local_previous_start + relative_time_offset

        return resolved_start.strftime("%Hh%M")

    if normalized_message in {
        "a la meme heure",
        "une heure plus tard",
        "une heure plus tot",
    }:
        if not context:
            return message

        previous_start_at = context.get("previous_start_at")

        if not previous_start_at:
            return message

        try:
            previous_start = datetime.fromisoformat(
                str(previous_start_at),
            )
        except ValueError:
            return message

        timezone = ZoneInfo(timezone_name)
        local_previous_start = previous_start.astimezone(timezone)

        if normalized_message == "une heure plus tard":
            local_previous_start += timedelta(hours=1)
        elif normalized_message == "une heure plus tot":
            local_previous_start -= timedelta(hours=1)

        return local_previous_start.strftime("%Hh%M")

    if normalized_message == "le lendemain":
        relative_days = 1
    elif normalized_message == "le surlendemain":
        relative_days = 2
    elif normalized_message == "la veille":
        relative_days = -1
    elif normalized_message == "l'avant-veille":
        relative_days = -2
    else:
        return message

    if not context:
        return message

    previous_date_text = context.get("requested_date_text")
    timezone = ZoneInfo(timezone_name)

    if previous_date_text:
        current = (
            now.astimezone(timezone)
            if now
            else datetime.now(timezone)
        )

        try:
            previous_date = parse_booking_date(
                date_text=str(previous_date_text),
                current=current,
            )
        except BookingDateTimeError:
            return message
    else:
        previous_start_at = context.get("previous_start_at")

        if not previous_start_at:
            return message

        try:
            previous_start = datetime.fromisoformat(
                str(previous_start_at),
            )
        except (TypeError, ValueError):
            return message

        previous_date = previous_start.astimezone(timezone).date()

    resolved_date = previous_date + timedelta(days=relative_days)

    return _format_booking_date(resolved_date)
