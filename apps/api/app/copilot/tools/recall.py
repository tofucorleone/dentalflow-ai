import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.appointment_service import clinic_timezone
from app.copilot.overdue_recall import (
    enrich_overdue_recall_patients,
    list_overdue_recall_patients,
)
from app.copilot.tools.response import (
    build_copilot_response,
)


def _normalize_recall_text(
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


def looks_like_recall_patients(
    message: str,
) -> bool:
    normalized = _normalize_recall_text(message)

    recall_markers = (
        "rappeler",
        "rappel",
        "recontacter",
        "recontact",
        "relancer",
        "relance",
        "pas revenu",
        "pas revenue",
        "n'est pas revenu",
        "n'est pas revenue",
        "ne sont pas revenus",
        "retard de controle",
        "suivi preventif",
    )

    patient_markers = (
        "qui",
        "patient",
        "patiente",
        "patients",
        "patientes",
        "quels",
        "quelles",
        "dois-je",
        "doit-on",
        "a recontacter",
        "a rappeler",
    )

    return (
        any(
            marker in normalized
            for marker in recall_markers
        )
        and any(
            marker in normalized
            for marker in patient_markers
        )
    )


def _format_recall_date(
    value: datetime,
    timezone: ZoneInfo,
) -> str:
    local_value = value.astimezone(timezone)

    return local_value.strftime("%d/%m/%Y")


async def answer_recall_patients(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )
    timezone = ZoneInfo(timezone_name)
    local_now = datetime.now(timezone)

    raw_patients = await list_overdue_recall_patients(
        cur=cur,
        clinic_id=clinic_id,
        now=local_now,
        minimum_months=12,
        limit=20,
    )

    patients = enrich_overdue_recall_patients(
        patients=raw_patients,
        now=local_now,
    )

    if not patients:
        return build_copilot_response(
            answer=(
                "Aucun patient actif n’est actuellement "
                "à recontacter selon le suivi préventif "
                "de plus de 12 mois."
            ),
            intent="recall",
            actions=[
                {
                    "type": "navigate",
                    "label": "Ouvrir le Copilote",
                    "href": "/copilot",
                }
            ],
            suggestions=[
                "Qui vient aujourd’hui ?",
                "Qui vient demain ?",
            ],
        )

    visible_patients = patients[:8]
    lines: list[str] = []
    actions: list[dict] = []
    sources: list[dict] = []

    for patient in visible_patients:
        patient_name = (
            patient.get("patient_name")
            or patient.get("phone")
            or "Patient sans nom"
        )

        last_completed_at = patient[
            "last_completed_at"
        ]
        last_visit = _format_recall_date(
            last_completed_at,
            timezone,
        )

        reasons = patient.get("reasons") or []
        main_reason = (
            reasons[0]
            if reasons
            else "Suivi préventif à programmer"
        )

        lines.append(
            f"• {patient_name} — dernière visite "
            f"le {last_visit} — {main_reason} "
            f"(score {patient['score']})"
        )

        actions.append(
            {
                "type": "navigate",
                "label": (
                    f"Ouvrir la fiche de {patient_name}"
                ),
                "href": (
                    f"/patients/{patient['patient_id']}"
                ),
            }
        )

        sources.append(
            {
                "type": "patient",
                "id": patient["patient_id"],
                "label": patient_name,
            }
        )

    count = len(patients)

    if count == 1:
        introduction = (
            "1 patient actif est à recontacter."
        )
    else:
        introduction = (
            f"{count} patients actifs sont à recontacter."
        )

    answer_parts = [
        introduction,
        "",
        *lines,
    ]

    if count > len(visible_patients):
        remaining = count - len(visible_patients)

        answer_parts.extend(
            [
                "",
                (
                    f"Et {remaining} autre"
                    f"{'s' if remaining > 1 else ''} "
                    "patient"
                    f"{'s' if remaining > 1 else ''} "
                    "dans le suivi préventif."
                ),
            ]
        )

    return build_copilot_response(
        answer="\n".join(answer_parts),
        intent="recall",
        actions=actions,
        sources=sources,
        suggestions=[
            "Ouvrir le Copilote",
            "Qui vient aujourd’hui ?",
            "Qui vient demain ?",
        ],
        requires_validation=False,
    )
