import re


def extract_selected_slot_index(message: str) -> int | None:
    text = message.lower().strip()

    if re.search(
        r"\b(?:le|la)\s+(?:dernier|dernière)\b",
        text,
    ):
        return -1

    ordinal_patterns = [
        (
            r"\b(?:le|la)\s+(?:premier|première)\b"
            r"|\b1(?:er|re|e|ème|eme)\b",
            1,
        ),
        (
            r"\b(?:le|la)\s+deuxième\b"
            r"|\b2(?:e|ème|eme)\b",
            2,
        ),
        (
            r"\b(?:le|la)\s+troisième\b"
            r"|\b3(?:e|ème|eme)\b",
            3,
        ),
        (
            r"\b(?:le|la)\s+quatrième\b"
            r"|\b4(?:e|ème|eme)\b",
            4,
        ),
    ]

    for pattern, index in ordinal_patterns:
        if re.search(pattern, text):
            return index

    numeric_match = re.search(
        r"\b(?:num[ée]ro|n[°ºo])\s*(\d+)\b",
        text,
    )

    if numeric_match:
        return int(numeric_match.group(1))

    return None
