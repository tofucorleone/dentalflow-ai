from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.ai.booking_datetime import normalize_text

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
from app.ai.time_preferences import TimePreference


def filter_suggested_slots(
    slots: list[dict[str, Any]],
    *,
    practitioner_id: UUID | str | None = None,
    date_text: str | None = None,
    preference: TimePreference | None = None,
) -> list[dict[str, Any]]:
    """
    Filtre une liste de créneaux déjà proposés.

    Cette fonction ne recherche aucun nouveau créneau et ne réserve rien.
    Elle travaille uniquement sur les données présentes dans suggested_slots.
    """

    filtered_slots = list(slots)

    if practitioner_id is not None:
        practitioner_id_text = str(practitioner_id)

        filtered_slots = [
            slot
            for slot in filtered_slots
            if str(slot.get("practitioner_id"))
            == practitioner_id_text
        ]

    if date_text:
        normalized_date = normalize_text(date_text)

        filtered_slots = [
            slot
            for slot in filtered_slots
            if _slot_matches_date(
                slot=slot,
                normalized_date=normalized_date,
            )
        ]

    if preference is not None:
        filtered_slots = [
            slot
            for slot in filtered_slots
            if _slot_matches_preference(
                slot=slot,
                preference=preference,
            )
        ]

    return filtered_slots


def _slot_matches_date(
    *,
    slot: dict[str, Any],
    normalized_date: str,
) -> bool:
    start_at_text = slot.get("start_at")

    if not start_at_text:
        return False

    try:
        start_at = datetime.fromisoformat(start_at_text)
    except (TypeError, ValueError):
        return False

    date_label = normalize_text(
        str(slot.get("date_label") or "")
    )

    accepted_values = {
        date_label,
        start_at.strftime("%d/%m/%Y"),
        start_at.strftime("%Y-%m-%d"),
        normalize_text(
            f"{start_at.day} "
            f"{MONTH_NAMES[start_at.month]}"
        ),
        normalize_text(
            f"{start_at.day} {MONTH_NAMES[start_at.month]} {start_at.year}"
        ),
    }

    return normalized_date in accepted_values


def _slot_matches_preference(
    *,
    slot: dict[str, Any],
    preference: TimePreference,
) -> bool:
    start_at_text = slot.get("start_at")

    if not start_at_text:
        return False

    try:
        start_at = datetime.fromisoformat(start_at_text)
    except (TypeError, ValueError):
        return False

    slot_time = start_at.time().replace(tzinfo=None)

    if preference.exact_time is not None:
        return (
            slot_time.hour == preference.exact_time.hour
            and slot_time.minute == preference.exact_time.minute
        )

    if (
        preference.earliest is not None
        and slot_time < preference.earliest
    ):
        return False

    if (
        preference.latest is not None
        and slot_time > preference.latest
    ):
        return False

    return True


__all__ = [
    "filter_suggested_slots",
]
