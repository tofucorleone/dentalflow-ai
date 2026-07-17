import re
from dataclasses import dataclass

from app.ai.booking_datetime import (
    MONTHS,
    WEEKDAYS,
    normalize_text,
)
from app.ai.schemas import ConversationIntent
from app.ai.time_preferences import (
    TimePreference,
    TimePreferenceError,
    parse_time_preference,
)


@dataclass(frozen=True, slots=True)
class MessageParts:
    intent: ConversationIntent | None = None
    date_text: str | None = None
    time_text: str | None = None
    time_preference: TimePreference | None = None
    treatment_text: str | None = None
    practitioner_text: str | None = None


_DATE_PATTERNS = (
    r"\baujourd'hui\b",
    r"\baujourdhui\b",
    r"\bapres[- ]demain\b",
    r"\b(?:la\s+)?semaine\s+prochaine\b",
    r"\b(?:en\s+)?debut\s+de\s+semaine\b",
    r"\b(?:en\s+)?fin\s+de\s+semaine\b",
    r"\bce\s+week-?end\b",
    r"\b(?:le\s+)?week-?end\s+prochain\b",
    r"\bdemain\b",
    r"\bdans\s+\d+\s+jours?\b",
    r"\bdans\s+(?:\d+|une|deux)\s+semaines?\b",
    (
        r"\b(?:"
        + "|".join(WEEKDAYS)
        + r")(?:\s+prochain)?\b"
    ),
    (
        r"\b(?:le\s+)?\d{1,2}\s+(?:"
        + "|".join(MONTHS)
        + r")(?:\s+\d{4})?\b"
    ),
)

_TIME_PREFERENCE_PATTERNS = (
    r"\b(?:plutot\s+|de preference\s+)?"
    r"(?:ce\s+matin|dans\s+la\s+matinee|matin)\b",
    r"\b(?:le\s+)?plus\s+tot\s+possible\b",
    r"\bpremier\s+creneau(?:\s+disponible)?\b",
    r"\bn[' ]importe\s+quand\b",
    r"\bquand\s+vous\s+voulez\b",
    r"\b(?:plutot\s+|de preference\s+)?"
    r"(?:dans\s+l[' ]apres-midi|l[' ]apres-midi|apres-midi)\b",
    r"\b(?:plutot\s+|de preference\s+)?"
    r"(?:en\s+)?fin\s+d[' ]apres-midi\b",
    r"\b(?:plutot\s+|de preference\s+)?"
    r"(?:en\s+)?fin\s+de\s+journee\b",
    r"\b(?:plutot\s+|de preference\s+)?(?:le\s+)?soir\b",
    r"\b(?:apres|a\s+partir\s+de)\s+"
    r"(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?\b",
    r"\bavant\s+"
    r"(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?\b",
    r"\bentre\s+"
    r"(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?"
    r"\s+et\s+"
    r"(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?\b",
)

_EXACT_TIME_PATTERN = (
    r"\b(?:a\s+|vers\s+|autour\s+de\s+)?"
    r"(?P<time>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)\b"
)

_PRACTITIONER_PATTERNS = (
    (
        r"\b(?:avec|voir|chez|prefere|preference pour)\s+"
        r"(?:le\s+)?(?:dr|docteur)\s+"
        r"(?P<name>[a-z][a-z'-]*)\b"
    ),
    (
        r"\b(?:avec|chez)\s+"
        r"(?P<name>[a-z][a-z'-]*)\b"
    ),
)


def _first_match(
    patterns: tuple[str, ...],
    text: str,
) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)

        if match is not None:
            return match.group(0).strip()

    return None


def _extract_practitioner_text(
    text: str,
) -> str | None:
    for pattern in _PRACTITIONER_PATTERNS:
        match = re.search(pattern, text)

        if match is not None:
            name = match.group("name").strip()

            if name in {
                "un",
                "une",
                "le",
                "la",
                "premier",
                "premiere",
                "praticien",
                "dentiste",
            }:
                continue

            return name

    return None


def extract_message_parts(message: str) -> MessageParts:
    normalized = normalize_text(message)
    practitioner_text = _extract_practitioner_text(
        normalized,
    )

    date_text = _first_match(
        _DATE_PATTERNS,
        normalized,
    )

    preference_text = _first_match(
        _TIME_PREFERENCE_PATTERNS,
        normalized,
    )

    if preference_text is not None:
        try:
            preference = parse_time_preference(
                preference_text,
            )
        except TimePreferenceError:
            preference = None
        else:
            return MessageParts(
                date_text=date_text,
                time_text=preference_text,
                time_preference=preference,
                practitioner_text=practitioner_text,
            )

    exact_time_match = re.search(
        _EXACT_TIME_PATTERN,
        normalized,
    )

    exact_time = (
        exact_time_match.group("time")
        if exact_time_match is not None
        else None
    )

    if exact_time is not None:
        try:
            preference = parse_time_preference(exact_time)
        except TimePreferenceError:
            preference = None
        else:
            return MessageParts(
                date_text=date_text,
                time_text=exact_time,
                time_preference=preference,
                practitioner_text=practitioner_text,
            )

    return MessageParts(
        date_text=date_text,
        practitioner_text=practitioner_text,
    )
