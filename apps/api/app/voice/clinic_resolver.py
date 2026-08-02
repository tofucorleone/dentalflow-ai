from app.ai.patient_matcher import normalize_phone
from app.db import connection


async def find_active_clinic_by_voice_number(
    called_number: str,
) -> dict | None:
    """
    Retrouve une clinique active à partir du numéro appelé.

    Le numéro Twilio reçu dans le champ `To` est normalisé avant
    comparaison avec clinics.phone.
    """

    normalized_number = normalize_phone(called_number)

    if not normalized_number:
        return None

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    name,
                    display_name,
                    phone,
                    timezone,
                    language
                FROM clinics
                WHERE active = TRUE
                  AND phone = %s
                LIMIT 1
                """,
                (normalized_number,),
            )

            return await cur.fetchone()


__all__ = [
    "find_active_clinic_by_voice_number",
]
