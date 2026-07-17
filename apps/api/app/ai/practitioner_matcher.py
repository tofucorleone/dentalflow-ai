import re
from uuid import UUID

from app.ai.booking_datetime import normalize_text
from app.practitioner_service import list_practitioners


_TITLE_PATTERN = re.compile(
    r"\b(?:dr|docteur|docteure)\s+",
)


def _name_variants(full_name: str) -> set[str]:
    normalized_full_name = normalize_text(full_name)
    without_title = _TITLE_PATTERN.sub(
        "",
        normalized_full_name,
    ).strip()

    variants = {
        normalized_full_name,
        without_title,
    }

    name_parts = without_title.split()

    if name_parts:
        variants.add(name_parts[-1])

    return {
        variant
        for variant in variants
        if len(variant) >= 2
    }


async def find_practitioner_in_message(
    clinic_id: UUID,
    message: str,
) -> dict | None:
    normalized_message = normalize_text(message)
    practitioners = await list_practitioners(
        clinic_id=clinic_id,
        include_inactive=False,
    )

    matches: list[tuple[int, dict]] = []

    for practitioner in practitioners:
        for variant in _name_variants(
            practitioner["full_name"],
        ):
            pattern = (
                r"(?<!\w)"
                + re.escape(variant)
                + r"(?!\w)"
            )

            if re.search(pattern, normalized_message):
                matches.append(
                    (
                        len(variant),
                        practitioner,
                    )
                )
                break

    if not matches:
        return None

    return max(
        matches,
        key=lambda match: match[0],
    )[1]
