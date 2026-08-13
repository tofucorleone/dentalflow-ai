import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


class BookingDateTimeError(ValueError):
    """Date ou heure conversationnelle invalide."""


WEEKDAYS = {
    "lundi": 0,
    "mardi": 1,
    "mercredi": 2,
    "jeudi": 3,
    "vendredi": 4,
    "samedi": 5,
    "dimanche": 6,
}

MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def next_weekday(
    current_date: date,
    target_weekday: int,
    force_next_week: bool = False,
) -> date:
    days_ahead = (target_weekday - current_date.weekday()) % 7

    if days_ahead == 0 or force_next_week:
        days_ahead += 7

    return current_date + timedelta(days=days_ahead)


def parse_booking_date(
    date_text: str,
    current: datetime,
) -> date:
    normalized_date = normalize_text(date_text)

    print(
        "[DEBUG][DATE]",
        {
            "raw": date_text,
            "normalized": normalized_date,
        },
        flush=True,
    )

    if normalized_date in {
        "la semaine d apres",
        "la semaine d'apres",
        "semaine d apres",
        "semaine d'apres",
    }:
        normalized_date = "la semaine prochaine"

    if normalized_date in {"aujourd'hui", "aujourdhui"}:
        return current.date()

    if normalized_date == "demain":
        return current.date() + timedelta(days=1)

    if normalized_date in {
        "apres-demain",
        "apres demain",
    }:
        return current.date() + timedelta(days=2)

    if normalized_date in {
        "la semaine prochaine",
        "semaine prochaine",
    }:
        days_until_monday = (
            7 - current.date().weekday()
        )

        return current.date() + timedelta(
            days=days_until_monday,
        )

    if normalized_date in {
        "en debut de semaine",
        "debut de semaine",
    }:
        return next_weekday(
            current_date=current.date(),
            target_weekday=WEEKDAYS["lundi"],
        )

    if normalized_date in {
        "en fin de semaine",
        "fin de semaine",
    }:
        return next_weekday(
            current_date=current.date(),
            target_weekday=WEEKDAYS["vendredi"],
        )

    if normalized_date in {
        "ce week-end",
        "ce weekend",
    }:
        return next_weekday(
            current_date=current.date(),
            target_weekday=WEEKDAYS["samedi"],
        )

    if normalized_date in {
        "le week-end prochain",
        "week-end prochain",
        "le weekend prochain",
        "weekend prochain",
    }:
        return next_weekday(
            current_date=current.date(),
            target_weekday=WEEKDAYS["samedi"],
            force_next_week=True,
        )

    relative_match = re.fullmatch(
        r"dans\s+(?P<days>\d+)\s+jours?",
        normalized_date,
    )

    if relative_match:
        days = int(relative_match.group("days"))

        if days <= 0:
            raise BookingDateTimeError(
                "Le nombre de jours doit être supérieur à zéro.",
            )

        return current.date() + timedelta(days=days)

    week_match = re.fullmatch(
        r"dans\s+(?P<weeks>\d+|une|deux)\s+semaines?",
        normalized_date,
    )

    if week_match:
        weeks_text = week_match.group("weeks")

        week_values = {
            "une": 1,
            "deux": 2,
        }

        weeks = (
            week_values[weeks_text]
            if weeks_text in week_values
            else int(weeks_text)
        )

        if weeks <= 0:
            raise BookingDateTimeError(
                "Le nombre de semaines doit être supérieur à zéro.",
            )

        return current.date() + timedelta(weeks=weeks)

    weekday_match = re.fullmatch(
        r"(?P<weekday>"
        + "|".join(WEEKDAYS)
        + r")(?P<next>\s+prochain)?",
        normalized_date,
    )

    if weekday_match:
        weekday = WEEKDAYS[weekday_match.group("weekday")]
        force_next_week = weekday_match.group("next") is not None

        return next_weekday(
            current_date=current.date(),
            target_weekday=weekday,
            force_next_week=force_next_week,
        )

    numeric_date_match = re.fullmatch(
        r"(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})",
        normalized_date,
    )

    if numeric_date_match:
        try:
            return date(
                year=int(numeric_date_match.group("year")),
                month=int(numeric_date_match.group("month")),
                day=int(numeric_date_match.group("day")),
            )
        except ValueError as exc:
            raise BookingDateTimeError(
                "La date indiquée n'est pas valide.",
            ) from exc

    explicit_date_match = re.fullmatch(
        r"(?:le\s+)?(?P<day>\d{1,2})\s+"
        r"(?P<month>"
        + "|".join(MONTHS)
        + r")(?:\s+(?P<year>\d{4}))?",
        normalized_date,
    )

    if explicit_date_match:
        day = int(explicit_date_match.group("day"))
        month = MONTHS[explicit_date_match.group("month")]
        year_text = explicit_date_match.group("year")
        year = int(year_text) if year_text else current.year

        try:
            requested_date = date(
                year=year,
                month=month,
                day=day,
            )
        except ValueError as exc:
            raise BookingDateTimeError(
                "La date indiquée n'est pas valide.",
            ) from exc

        if not year_text and requested_date < current.date():
            try:
                requested_date = requested_date.replace(
                    year=year + 1,
                )
            except ValueError as exc:
                raise BookingDateTimeError(
                    "La date indiquée n'est pas valide.",
                ) from exc

        return requested_date

    raise BookingDateTimeError(
        "Je comprends les dates comme « demain », « après-demain », "
        "« la semaine prochaine », « vendredi », « lundi prochain », "
        "« dans 2 jours » ou « le 24 juillet ».",
    )


def parse_booking_datetime(
    date_text: str,
    time_text: str,
    timezone_name: str,
    now: datetime | None = None,
) -> datetime:
    timezone = ZoneInfo(timezone_name)
    current = now.astimezone(timezone) if now else datetime.now(timezone)

    requested_date = parse_booking_date(
        date_text=date_text,
        current=current,
    )

    normalized_time = normalize_text(time_text)

    match = re.fullmatch(
        r"(?P<hour>[01]?\d|2[0-3])(?:h|:)(?P<minute>[0-5]\d)?",
        normalized_time,
    )

    if match is None:
        raise BookingDateTimeError(
            "L'heure doit être indiquée comme 15h, 15h30 ou 15:30.",
        )

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)

    result = datetime(
        year=requested_date.year,
        month=requested_date.month,
        day=requested_date.day,
        hour=hour,
        minute=minute,
        tzinfo=timezone,
    )

    if result <= current:
        raise BookingDateTimeError(
            "Le créneau demandé doit être dans le futur.",
        )

    return result
