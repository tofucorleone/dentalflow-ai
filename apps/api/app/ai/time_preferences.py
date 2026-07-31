import re
from dataclasses import dataclass
from datetime import time

from app.ai.booking_datetime import normalize_text


class TimePreferenceError(ValueError):
    """Préférence horaire conversationnelle invalide."""


@dataclass(frozen=True, slots=True)
class TimePreference:
    exact_time: time | None = None
    earliest: time | None = None
    latest: time | None = None


_PERIODS: dict[str, TimePreference] = {
    "matin": TimePreference(
        earliest=time(8, 0),
        latest=time(12, 0),
    ),
    "ce matin": TimePreference(
        earliest=time(8, 0),
        latest=time(12, 0),
    ),
    "dans la matinee": TimePreference(
        earliest=time(8, 0),
        latest=time(12, 0),
    ),
    "apres-midi": TimePreference(
        earliest=time(13, 0),
        latest=time(18, 0),
    ),
    "l'apres-midi": TimePreference(
        earliest=time(13, 0),
        latest=time(18, 0),
    ),
    "dans l'apres-midi": TimePreference(
        earliest=time(13, 0),
        latest=time(18, 0),
    ),
    "fin d'apres-midi": TimePreference(
        earliest=time(16, 0),
        latest=time(18, 0),
    ),
    "en fin d'apres-midi": TimePreference(
        earliest=time(16, 0),
        latest=time(18, 0),
    ),
    "fin de journee": TimePreference(
        earliest=time(17, 0),
        latest=time(20, 0),
    ),
    "en fin de journee": TimePreference(
        earliest=time(17, 0),
        latest=time(20, 0),
    ),
    "apres le travail": TimePreference(
        earliest=time(17, 0),
        latest=time(20, 0),
    ),
    "soir": TimePreference(
        earliest=time(18, 0),
        latest=time(22, 0),
    ),
    "le soir": TimePreference(
        earliest=time(18, 0),
        latest=time(22, 0),
    ),
    "le plus tot possible": TimePreference(
        earliest=time(8, 0),
    ),
    "plus tot possible": TimePreference(
        earliest=time(8, 0),
    ),
    "premier creneau": TimePreference(
        earliest=time(8, 0),
    ),
    "premier creneau disponible": TimePreference(
        earliest=time(8, 0),
    ),
    "n'importe quand": TimePreference(
        earliest=time(8, 0),
    ),
    "quand vous voulez": TimePreference(
        earliest=time(8, 0),
    ),
}


def _parse_time_value(value: str) -> time:
    match = re.fullmatch(
        r"(?P<hour>[01]?\d|2[0-3])"
        r"(?:h|:)"
        r"(?P<minute>[0-5]\d)?",
        value,
    )

    if match is None:
        raise TimePreferenceError(
            "L'heure doit être indiquée comme 15h, 15h30 ou 15:30.",
        )

    return time(
        hour=int(match.group("hour")),
        minute=int(match.group("minute") or 0),
    )


def parse_time_preference(value: str) -> TimePreference:
    normalized = normalize_text(value)

    normalized = re.sub(
        r"^(?:plutot|de preference)\s+",
        "",
        normalized,
    ).strip()

    period = _PERIODS.get(normalized)

    if period is not None:
        return period

    exact_match = re.fullmatch(
        r"(?P<time>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)",
        normalized,
    )

    if exact_match:
        return TimePreference(
            exact_time=_parse_time_value(exact_match.group("time")),
        )

    after_match = re.fullmatch(
        r"(?:apres|a partir de)\s+"
        r"(?P<time>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)",
        normalized,
    )

    if after_match:
        return TimePreference(
            earliest=_parse_time_value(after_match.group("time")),
        )

    before_match = re.fullmatch(
        r"avant\s+"
        r"(?P<time>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)",
        normalized,
    )

    if before_match:
        return TimePreference(
            latest=_parse_time_value(before_match.group("time")),
        )

    range_match = re.fullmatch(
        r"entre\s+"
        r"(?P<start>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)"
        r"\s+et\s+"
        r"(?P<end>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)",
        normalized,
    )

    if range_match:
        start = _parse_time_value(range_match.group("start"))
        end = _parse_time_value(range_match.group("end"))

        if start >= end:
            raise TimePreferenceError(
                "L'heure de début doit précéder l'heure de fin.",
            )

        return TimePreference(
            earliest=start,
            latest=end,
        )

    approximate_match = re.fullmatch(
        r"(?:vers|autour de)\s+"
        r"(?P<time>(?:[01]?\d|2[0-3])(?:h|:)(?:[0-5]\d)?)",
        normalized,
    )

    if approximate_match:
        return TimePreference(
            exact_time=_parse_time_value(
                approximate_match.group("time"),
            ),
        )

    raise TimePreferenceError(
        "Je comprends les préférences comme « le matin », "
        "« l'après-midi », « après 17h », « avant 11h », "
        "« entre 14h et 16h » ou « vers 15h ».",
    )


def format_time_preference_label(
    date_text: str,
    preference_text: str,
) -> str:
    normalized = normalize_text(preference_text)

    labels = {
        "matin": "matin",
        "ce matin": "le matin",
        "dans la matinee": "dans la matinée",
        "apres-midi": "après-midi",
        "l'apres-midi": "l'après-midi",
        "dans l'apres-midi": "dans l'après-midi",
        "fin d'apres-midi": "en fin d'après-midi",
        "en fin d'apres-midi": "en fin d'après-midi",
        "fin de journee": "en fin de journée",
        "en fin de journee": "en fin de journée",
        "soir": "le soir",
        "le soir": "le soir",
        "le plus tot possible": "dès que possible",
        "plus tot possible": "dès que possible",
        "premier creneau": "au premier créneau disponible",
        "premier creneau disponible": (
            "au premier créneau disponible"
        ),
        "n'importe quand": "à n'importe quelle heure",
        "quand vous voulez": "à l'heure qui vous convient",
        "apres 17h": "après 17h",
    }

    normalized = re.sub(
        r"^(?:plutot|de preference)\s+",
        "",
        normalized,
    ).strip()

    readable_preference = labels.get(
        normalized,
        preference_text.strip(),
    )

    if normalized in {
        "le plus tot possible",
        "plus tot possible",
    }:
        return (
            f"{readable_preference} {date_text.strip()}"
        ).strip()

    if normalized in {
        "premier creneau",
        "premier creneau disponible",
    }:
        return date_text.strip()

    if normalized == "matin":
        readable_preference = "le matin"

    return f"{date_text.strip()} {readable_preference}".strip()

