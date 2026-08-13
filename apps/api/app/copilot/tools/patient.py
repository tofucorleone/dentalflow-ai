from app.copilot.tools.response import build_copilot_response

import re


def extract_patient_search_query(
    message: str,
) -> str:
    cleaned = " ".join(message.strip().split())

    patterns = (
        r"^ouvre(?:-moi)?\s+(?:la\s+)?fiche\s+(?:du\s+patient\s+|de\s+)?",
        r"^ouvre(?:-moi)?\s+(?:le\s+)?dossier\s+(?:du\s+patient\s+|de\s+)?",
        r"^affiche(?:-moi)?\s+(?:la\s+)?fiche\s+(?:du\s+patient\s+|de\s+)?",
        r"^affiche(?:-moi)?\s+(?:le\s+)?dossier\s+(?:du\s+patient\s+|de\s+)?",
        r"^affiche(?:-moi)?\s+(?:le\s+patient\s+)?",
        r"^trouve(?:-moi)?\s+(?:le\s+patient\s+|la\s+patiente\s+)?",
        r"^cherche(?:-moi)?\s+(?:le\s+patient\s+|la\s+patiente\s+)?",
        r"^patient\s+",
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

    return cleaned.strip(" ?.!,:;")


async def search_copilot_patients(
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
            phone,
            email,
            active
        FROM patients
        WHERE clinic_id = %s
          AND active = TRUE
          AND (
              full_name ILIKE %s
              OR phone ILIKE %s
              OR email ILIKE %s
          )
        ORDER BY
            CASE
                WHEN LOWER(full_name) = LOWER(%s)
                THEN 0
                ELSE 1
            END,
            full_name NULLS LAST,
            updated_at DESC
        LIMIT %s
        """,
        (
            clinic_id,
            search_pattern,
            search_pattern,
            search_pattern,
            cleaned_query,
            safe_limit,
        ),
    )

    return await cur.fetchall()


async def answer_patient_lookup(
    *,
    cur,
    clinic_id,
    message: str,
) -> dict:
    patient_query = extract_patient_search_query(
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
                f"Aucun patient actif trouvé pour "
                f"« {patient_query} »."
            ),
            intent="patient_search",
            suggestions=[
                "Ouvrir la liste des patients",
            ],
        )

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
                    f"Ouvrir la fiche de {patient_name}"
                ),
                "href": f"/patients/{patient['id']}",
            }
        )

        sources.append(
            {
                "type": "patient",
                "id": patient["id"],
                "label": patient_name,
            }
        )

    if len(patients) == 1:
        patient_name = sources[0]["label"]

        answer = (
            f"J’ai trouvé {patient_name}. "
            "Vous pouvez ouvrir sa fiche patient."
        )
        intent = "open_patient"
    else:
        answer = (
            f"J’ai trouvé {len(patients)} patients "
            f"correspondant à « {patient_query} ». "
            "Choisissez la fiche à ouvrir."
        )
        intent = "patient_search"

    suggestions = [
        "Ouvrir la liste des patients",
        "Qui vient aujourd’hui ?",
    ]

    return build_copilot_response(
        answer=answer,
        intent=intent,
        actions=actions,
        sources=sources,
        suggestions=suggestions,
    )


def looks_like_patient_lookup(
    message: str,
) -> bool:
    normalized = " ".join(
        message.strip().lower().split()
    )

    markers = (
        "ouvre",
        "affiche",
        "fiche",
        "dossier",
        "patient",
        "patiente",
        "trouve",
        "cherche",
    )

    return any(
        marker in normalized
        for marker in markers
    )
