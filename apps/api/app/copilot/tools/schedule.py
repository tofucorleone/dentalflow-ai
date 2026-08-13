from datetime import datetime, time, timedelta
import unicodedata
from zoneinfo import ZoneInfo

from app.appointment_service import (
    clinic_timezone,
    list_appointments_for_period,
)
from app.copilot.tools.response import (
    build_copilot_response,
)


def _normalize_text(value: str | None) -> str:
    normalized = (
        (value or "")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("`", "'")
        .strip()
        .lower()
    )

    return "".join(
        character
        for character in unicodedata.normalize(
            "NFKD",
            normalized,
        )
        if not unicodedata.combining(character)
    )


def extract_schedule_period(
    message: str,
) -> str | None:
    normalized = _normalize_text(message)

    tomorrow_markers = (
        "demain",
        "jour suivant",
        "lendemain",
    )

    today_markers = (
        "aujourd'hui",
        "aujourdhui",
        "ce jour",
        "du jour",
    )

    if any(
        marker in normalized
        for marker in tomorrow_markers
    ):
        return "tomorrow"

    if any(
        marker in normalized
        for marker in today_markers
    ):
        return "today"

    return None


def looks_like_schedule(
    message: str,
) -> bool:
    normalized = _normalize_text(message)
    period = extract_schedule_period(message)

    schedule_markers = (
        "rendez-vous",
        "rendez vous",
        "rdv",
        "planning",
        "agenda",
        "qui vient",
        "combien",
        "patients prevus",
        "patients attendus",
    )

    return (
        period is not None
        and any(
            marker in normalized
            for marker in schedule_markers
        )
    )


# Ancien nom conservé pour compatibilité.
def looks_like_today_schedule(
    message: str,
) -> bool:
    return (
        extract_schedule_period(message) == "today"
        and looks_like_schedule(message)
    )


async def get_schedule_for_period(
    *,
    cur,
    clinic_id,
    period: str,
    now: datetime | None = None,
) -> tuple[str, datetime, list[dict]]:
    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )
    timezone = ZoneInfo(timezone_name)

    local_now = (
        now.astimezone(timezone)
        if now is not None
        else datetime.now(timezone)
    )

    if period == "today":
        target_date = local_now.date()
    elif period == "tomorrow":
        target_date = (
            local_now.date()
            + timedelta(days=1)
        )
    else:
        raise ValueError(
            f"Période de planning inconnue : {period}"
        )

    period_start = datetime.combine(
        target_date,
        time.min,
        tzinfo=timezone,
    )
    period_end = (
        period_start
        + timedelta(days=1)
    )

    appointments = await list_appointments_for_period(
        cur=cur,
        clinic_id=clinic_id,
        date_from=period_start,
        date_to=period_end,
        limit=500,
    )

    active_appointments = [
        appointment
        for appointment in appointments
        if appointment.get("status")
        in {"pending", "confirmed"}
    ]

    return (
        timezone_name,
        local_now,
        active_appointments,
    )


# Ancienne fonction conservée pour compatibilité.
async def get_today_schedule(
    *,
    cur,
    clinic_id,
    now: datetime | None = None,
) -> tuple[str, datetime, list[dict]]:
    return await get_schedule_for_period(
        cur=cur,
        clinic_id=clinic_id,
        period="today",
        now=now,
    )


def _period_labels(
    period: str,
) -> tuple[str, str]:
    if period == "tomorrow":
        return (
            "demain",
            "de demain",
        )

    return (
        "aujourd’hui",
        "du jour",
    )


async def answer_schedule(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    period = (
        extract_schedule_period(message)
        or "today"
    )

    (
        timezone_name,
        _local_now,
        appointments,
    ) = await get_schedule_for_period(
        cur=cur,
        clinic_id=clinic_id,
        period=period,
    )

    period_label, period_context = (
        _period_labels(period)
    )

    if not appointments:
        suggestions = (
            [
                "Qui vient aujourd’hui ?",
                "Ouvrir le calendrier",
            ]
            if period == "tomorrow"
            else [
                "Qui vient demain ?",
                "Quel est le prochain rendez-vous du Dr Sara ?",
            ]
        )

        return build_copilot_response(
            answer=(
                "Aucun rendez-vous actif n’est "
                f"planifié {period_label}."
            ),
            intent="schedule",
            actions=[
                {
                    "type": "navigate",
                    "label": "Ouvrir le calendrier",
                    "href": "/appointments",
                }
            ],
            suggestions=suggestions,
        )

    timezone = ZoneInfo(timezone_name)
    lines: list[str] = []

    for appointment in appointments[:8]:
        local_start = appointment[
            "start_at"
        ].astimezone(timezone)

        formatted_time = local_start.strftime(
            "%H:%M"
        )

        patient_name = (
            appointment.get("patient_name")
            or "Patient sans nom"
        )

        practitioner_name = (
            appointment.get(
                "practitioner_name"
            )
            or "Praticien non attribué"
        )

        treatment_name = appointment.get(
            "treatment_name"
        )

        treatment_suffix = (
            f" — {treatment_name}"
            if treatment_name
            else ""
        )

        lines.append(
            f"{formatted_time} — {patient_name} "
            f"avec {practitioner_name}"
            f"{treatment_suffix}"
        )

    count = len(appointments)

    if count == 1:
        introduction = (
            "Il y a 1 rendez-vous actif "
            f"{period_label}."
        )
    else:
        introduction = (
            f"Il y a {count} rendez-vous actifs "
            f"{period_label}."
        )

    answer_parts = [
        introduction,
        "",
        *lines,
    ]

    if count > len(lines):
        remaining = count - len(lines)

        answer_parts.extend(
            [
                "",
                (
                    f"Et {remaining} autre"
                    f"{'s' if remaining > 1 else ''} "
                    f"rendez-vous dans le planning "
                    f"{period_context}."
                ),
            ]
        )

    sources = [
        {
            "type": "appointment",
            "id": appointment["id"],
            "label": (
                "Rendez-vous de "
                + (
                    appointment.get(
                        "patient_name"
                    )
                    or "Patient sans nom"
                )
            ),
        }
        for appointment in appointments
    ]

    suggestions = (
        [
            "Qui vient aujourd’hui ?",
            "Ouvrir le calendrier",
        ]
        if period == "tomorrow"
        else [
            "Qui vient demain ?",
            "Quel est le prochain rendez-vous du Dr Sara ?",
        ]
    )

    return build_copilot_response(
        answer="\n".join(answer_parts),
        intent="schedule",
        actions=[
            {
                "type": "navigate",
                "label": "Ouvrir le calendrier",
                "href": "/appointments",
            }
        ],
        sources=sources,
        suggestions=suggestions,
    )


# Ancien exécuteur conservé pour compatibilité.
async def answer_today_schedule(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    return await answer_schedule(
        cur=cur,
        clinic_id=clinic_id,
        message=message,
    )
