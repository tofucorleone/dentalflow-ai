import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.appointment_service import (
    clinic_timezone,
    get_next_patient_appointment,
)
from app.copilot.tools.patient import (
    search_copilot_patients,
)
from app.copilot.tools.response import (
    build_copilot_response,
)


def _normalize_text(
    value: str | None,
) -> str:
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


def _format_french_date(
    value: datetime,
) -> str:
    weekdays = (
        "lundi",
        "mardi",
        "mercredi",
        "jeudi",
        "vendredi",
        "samedi",
        "dimanche",
    )

    months = (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    )

    return (
        f"{weekdays[value.weekday()]} "
        f"{value.day} "
        f"{months[value.month - 1]} "
        f"{value.year}"
    )


def looks_like_next_patient_appointment(
    message: str,
) -> bool:
    normalized = _normalize_text(message)

    appointment_markers = (
        "rendez-vous",
        "rendez vous",
        "rdv",
        "revient",
        "revenir",
    )

    next_markers = (
        "prochain",
        "prochaine",
        "quand",
        "quel jour",
        "revient",
    )

    practitioner_markers = (
        "dr ",
        "docteur ",
        "praticien",
        "praticienne",
    )

    has_appointment_signal = any(
        marker in normalized
        for marker in appointment_markers
    )

    has_next_signal = any(
        marker in normalized
        for marker in next_markers
    )

    explicitly_targets_practitioner = any(
        marker in normalized
        for marker in practitioner_markers
    )

    return (
        has_appointment_signal
        and has_next_signal
        and not explicitly_targets_practitioner
    )


def extract_patient_appointment_query(
    message: str,
) -> str:
    cleaned = " ".join(message.strip().split())

    patterns = (
        (
            r"^quand\s+(?:est\s+)?"
            r"(?:le\s+)?prochain(?:e)?\s+"
            r"(?:rendez[- ]vous|rdv)\s+"
            r"(?:du|de la|de l'|de)\s+"
        ),
        (
            r"^(?:c['’]\s*est\s+)?quand\s+"
            r"(?:le\s+)?prochain(?:e)?\s+"
            r"(?:rendez[- ]vous|rdv)\s+"
            r"(?:du|de la|de l'|de)\s+"
        ),
        (
            r"^(?:le\s+)?prochain(?:e)?\s+"
            r"(?:rendez[- ]vous|rdv)\s+"
            r"(?:du|de la|de l'|de)\s+"
        ),
        (
            r"^(?:affiche|montre|trouve)"
            r"(?:-moi)?\s+"
            r"(?:le\s+)?prochain(?:e)?\s+"
            r"(?:rendez[- ]vous|rdv)\s+"
            r"(?:du|de la|de l'|de)\s+"
        ),
        r"^quand\s+revient\s+",
    )

    for pattern in patterns:
        updated = re.sub(
            pattern,
            "",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )

        if updated != cleaned:
            cleaned = updated.strip()
            break

    cleaned = re.sub(
        (
            r"\b("
            r"a\s+(?:son\s+)?(?:prochain\s+)?"
            r"(?:rendez[- ]vous|rdv)\s+quand"
            r"|revient\s+quand"
            r"|revient\s+quel\s+jour"
            r"|a\s+rendez[- ]vous\s+quand"
            r")\b"
        ),
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\b(patient|patiente)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = " ".join(cleaned.split())

    return cleaned.strip(" ?.!,:;")


async def answer_next_patient_appointment(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    patient_query = extract_patient_appointment_query(
        message
    )

    patients = await search_copilot_patients(
        cur=cur,
        clinic_id=clinic_id,
        query=patient_query,
        limit=5,
    )

    if not patients:
        return build_copilot_response(
            answer=(
                "Aucun patient actif trouvé pour "
                f"« {patient_query} »."
            ),
            intent="patient_next_appointment",
            suggestions=[
                "Ouvrir la liste des patients",
                "Qui vient aujourd’hui ?",
            ],
        )

    if len(patients) > 1:
        actions = []
        sources = []

        for patient in patients:
            patient_name = (
                patient.get("full_name")
                or patient.get("phone")
                or "Patient sans nom"
            )

            actions.append(
                {
                    "type": "navigate",
                    "label": (
                        f"Ouvrir la fiche de "
                        f"{patient_name}"
                    ),
                    "href": (
                        f"/patients/{patient['id']}"
                    ),
                }
            )

            sources.append(
                {
                    "type": "patient",
                    "id": patient["id"],
                    "label": patient_name,
                }
            )

        return build_copilot_response(
            answer=(
                f"J’ai trouvé {len(patients)} patients "
                f"correspondant à « {patient_query} ». "
                "Précisez lequel vous recherchez."
            ),
            intent="patient_next_appointment",
            actions=actions,
            sources=sources,
            suggestions=[
                "Ouvrir la liste des patients",
            ],
        )

    patient = patients[0]

    patient_name = (
        patient.get("full_name")
        or patient.get("phone")
        or "Patient sans nom"
    )

    appointment = await get_next_patient_appointment(
        clinic_id=clinic_id,
        patient_id=patient["id"],
    )

    patient_source = {
        "type": "patient",
        "id": patient["id"],
        "label": patient_name,
    }

    patient_action = {
        "type": "navigate",
        "label": (
            f"Ouvrir la fiche de {patient_name}"
        ),
        "href": f"/patients/{patient['id']}",
    }

    calendar_action = {
        "type": "navigate",
        "label": "Ouvrir le calendrier",
        "href": "/appointments",
    }

    if appointment is None:
        return build_copilot_response(
            answer=(
                f"Aucun rendez-vous futur actif n’est "
                f"planifié pour {patient_name}."
            ),
            intent="patient_next_appointment",
            actions=[
                patient_action,
                calendar_action,
            ],
            sources=[
                patient_source,
            ],
            suggestions=[
                f"Ouvre la fiche de {patient_name}",
                "Qui vient aujourd’hui ?",
            ],
        )

    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )
    timezone = ZoneInfo(timezone_name)

    local_start = appointment["start_at"].astimezone(
        timezone
    )

    formatted_date = _format_french_date(
        local_start
    )
    formatted_time = local_start.strftime("%H:%M")

    practitioner_name = (
        appointment.get("practitioner_name")
        or "un praticien non attribué"
    )

    treatment_name = appointment.get(
        "treatment_name"
    )

    treatment_sentence = (
        f" pour {treatment_name}"
        if treatment_name
        else ""
    )

    return build_copilot_response(
        answer=(
            f"Le prochain rendez-vous de "
            f"{patient_name} est prévu le "
            f"{formatted_date} à {formatted_time} "
            f"avec {practitioner_name}"
            f"{treatment_sentence}."
        ),
        intent="patient_next_appointment",
        actions=[
            patient_action,
            calendar_action,
        ],
        sources=[
            patient_source,
            {
                "type": "appointment",
                "id": appointment["id"],
                "label": (
                    f"Rendez-vous du {formatted_date} "
                    f"à {formatted_time}"
                ),
            },
        ],
        suggestions=[
            f"Ouvre la fiche de {patient_name}",
            (
                "Quel est le prochain rendez-vous du "
                f"{practitioner_name} ?"
            ),
            "Qui vient aujourd’hui ?",
        ],
    )
