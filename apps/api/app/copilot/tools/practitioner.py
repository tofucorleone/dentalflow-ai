import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.appointment_service import clinic_timezone
from app.copilot.tools.response import build_copilot_response


def _normalize_match_text(value: str | None) -> str:
    import unicodedata

    normalized = (value or "").strip().lower()

    return "".join(
        character
        for character in unicodedata.normalize(
            "NFKD",
            normalized,
        )
        if not unicodedata.combining(character)
    )


def _format_french_date(value: datetime) -> str:
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
        f"{value.day} "
        f"{months[value.month - 1]} "
        f"{value.year}"
    )


def extract_practitioner_search_query(
    message: str,
) -> str:
    cleaned = " ".join(message.strip().split())

    cleaned = re.sub(
        r"\b(rendez[- ]vous|rdv|patient|prochain|prochaine|"
        r"ensuite|apres|après|quand|quel|quelle|qui|est|"
        r"le|la|les|du|de|des|pour|avec|a|à|travaille|"
        r"recoit|reçoit|voir|montre|affiche)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\b(docteur|dr\.?|praticien|praticienne)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\b(elle|il|lui|eux|elles|on|nous|vous|moi|toi)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = " ".join(cleaned.split())

    return cleaned.strip(" ?.!,:;")


def looks_like_next_practitioner_appointment(
    message: str,
) -> bool:
    normalized = _normalize_match_text(message)

    appointment_markers = (
        "rendez-vous",
        "rendez vous",
        "rdv",
        "prochain patient",
        "prochaine patiente",
        "qui ensuite",
        "qui apres",
        "travaille quand",
        "recoit quand",
    )

    practitioner_markers = (
        "dr ",
        "docteur ",
        "praticien",
        "praticienne",
    )

    return (
        any(
            marker in normalized
            for marker in appointment_markers
        )
        and any(
            marker in normalized
            for marker in practitioner_markers
        )
    )


async def search_copilot_practitioners(
    *,
    cur,
    clinic_id,
    query: str,
    limit: int = 5,
) -> list[dict]:
    cleaned_query = " ".join(query.strip().split())

    if not cleaned_query:
        return []

    safe_limit = min(max(limit, 1), 10)
    search_pattern = f"%{cleaned_query}%"

    await cur.execute(
        """
        SELECT
            id,
            full_name,
            active
        FROM practitioners
        WHERE clinic_id = %s
          AND active = TRUE
          AND full_name ILIKE %s
        ORDER BY
            CASE
                WHEN LOWER(full_name) = LOWER(%s)
                THEN 0
                ELSE 1
            END,
            full_name
        LIMIT %s
        """,
        (
            clinic_id,
            search_pattern,
            cleaned_query,
            safe_limit,
        ),
    )

    return await cur.fetchall()


async def get_next_practitioner_appointment(
    *,
    cur,
    clinic_id,
    practitioner_id,
    now: datetime,
) -> dict | None:
    await cur.execute(
        """
        SELECT
            a.id,
            a.patient_id,
            a.practitioner_id,
            a.treatment_id,
            a.status,
            a.start_at,
            a.end_at,
            p.full_name AS patient_name,
            pr.full_name AS practitioner_name,
            t.name AS treatment_name
        FROM appointments a
        JOIN patients p
          ON p.id = a.patient_id
         AND p.clinic_id = a.clinic_id
        JOIN practitioners pr
          ON pr.id = a.practitioner_id
         AND pr.clinic_id = a.clinic_id
        LEFT JOIN treatments t
          ON t.id = a.treatment_id
         AND t.clinic_id = a.clinic_id
        WHERE a.clinic_id = %s
          AND a.practitioner_id = %s
          AND a.status IN ('pending', 'confirmed')
          AND a.start_at >= %s
        ORDER BY a.start_at
        LIMIT 1
        """,
        (
            clinic_id,
            practitioner_id,
            now,
        ),
    )

    return await cur.fetchone()


async def answer_next_practitioner_appointment(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    practitioner_query = extract_practitioner_search_query(
        message
    )

    practitioners = await search_copilot_practitioners(
        cur=cur,
        clinic_id=clinic_id,
        query=practitioner_query,
        limit=5,
    )

    if not practitioners:
        return build_copilot_response(
            answer=(
                "Aucun praticien actif trouvé pour "
                f"« {practitioner_query} »."
            ),
            intent="practitioner_search",
            actions=[
                {
                    "type": "navigate",
                    "label": "Voir les praticiens",
                    "href": "/practitioners",
                }
            ],
            suggestions=[
                "Ouvrir les praticiens",
                "Qui vient aujourd’hui ?",
            ],
        )

    if len(practitioners) > 1:
        actions = []
        sources = []

        for practitioner in practitioners:
            practitioner_name = (
                practitioner.get("full_name")
                or "Praticien sans nom"
            )

            actions.append(
                {
                    "type": "navigate",
                    "label": f"Voir {practitioner_name}",
                    "href": "/practitioners",
                }
            )

            sources.append(
                {
                    "type": "practitioner",
                    "id": practitioner["id"],
                    "label": practitioner_name,
                }
            )

        return build_copilot_response(
            answer=(
                f"J’ai trouvé {len(practitioners)} "
                "praticiens correspondants. "
                "Précisez lequel vous recherchez."
            ),
            intent="practitioner_search",
            actions=actions,
            sources=sources,
            suggestions=[
                "Ouvrir les praticiens",
            ],
        )

    practitioner = practitioners[0]
    practitioner_name = (
        practitioner.get("full_name")
        or "le praticien"
    )

    timezone_name = await clinic_timezone(
        cur,
        clinic_id,
    )
    timezone = ZoneInfo(timezone_name)
    local_now = datetime.now(timezone)

    appointment = await get_next_practitioner_appointment(
        cur=cur,
        clinic_id=clinic_id,
        practitioner_id=practitioner["id"],
        now=local_now,
    )

    practitioner_source = {
        "type": "practitioner",
        "id": practitioner["id"],
        "label": practitioner_name,
    }

    if appointment is None:
        return build_copilot_response(
            answer=(
                f"Aucun rendez-vous futur actif n’est "
                f"planifié pour {practitioner_name}."
            ),
            intent="next_practitioner_appointment",
            actions=[
                {
                    "type": "navigate",
                    "label": "Ouvrir le calendrier",
                    "href": "/appointments",
                }
            ],
            sources=[practitioner_source],
            suggestions=[
                "Qui vient aujourd’hui ?",
                "Ouvrir les praticiens",
            ],
        )

    local_start = appointment["start_at"].astimezone(
        timezone
    )
    formatted_date = _format_french_date(local_start)
    formatted_time = local_start.strftime("%H:%M")

    patient_name = (
        appointment.get("patient_name")
        or "un patient"
    )
    treatment_name = appointment.get("treatment_name")

    treatment_sentence = (
        f" pour {treatment_name}"
        if treatment_name
        else ""
    )

    return build_copilot_response(
        answer=(
            f"Le prochain rendez-vous de "
            f"{practitioner_name} est prévu "
            f"le {formatted_date} à {formatted_time} "
            f"avec {patient_name}"
            f"{treatment_sentence}."
        ),
        intent="next_practitioner_appointment",
        actions=[
            {
                "type": "navigate",
                "label": "Ouvrir le calendrier",
                "href": "/appointments",
            },
            {
                "type": "navigate",
                "label": (
                    f"Ouvrir la fiche de {patient_name}"
                ),
                "href": (
                    f"/patients/{appointment['patient_id']}"
                ),
            },
        ],
        sources=[
            practitioner_source,
            {
                "type": "appointment",
                "id": appointment["id"],
                "label": (
                    f"Rendez-vous du {formatted_date} "
                    f"à {formatted_time}"
                ),
            },
            {
                "type": "patient",
                "id": appointment["patient_id"],
                "label": patient_name,
            },
        ],
        suggestions=[
            f"Ouvre la fiche de {patient_name}",
            "Qui vient aujourd’hui ?",
        ],
    )
