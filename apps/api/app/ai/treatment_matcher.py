from uuid import UUID

from app.ai.booking_datetime import normalize_text
from app.treatment_service import list_active_treatments


async def find_treatment_in_message(
    clinic_id: UUID,
    message: str,
) -> dict | None:
    normalized_message = normalize_text(message)

    treatments = await list_active_treatments(clinic_id)

    matches: list[dict] = []

    for treatment in treatments:
        normalized_name = normalize_text(treatment["name"])

        if normalized_name in normalized_message:
            matches.append(treatment)

    if not matches:
        return None

    return max(
        matches,
        key=lambda treatment: len(
            normalize_text(treatment["name"])
        ),
    )
