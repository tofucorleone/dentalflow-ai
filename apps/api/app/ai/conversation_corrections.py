import re

from app.ai.booking_datetime import normalize_text


def is_correction_message(message: str) -> bool:
    normalized = normalize_text(message)

    correction_patterns = (
        r"^finalement\b",
        r"^en\s+fait\b",
        r"^ah\s+non\b",
        r"^non\s*,?\s+plutot\b",
        r"^plutot\b",
    )

    return any(
        re.search(pattern, normalized)
        for pattern in correction_patterns
    )
