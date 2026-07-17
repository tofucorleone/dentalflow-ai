import re
from uuid import UUID

from app.db import connection


def normalize_phone(phone: str) -> str:
    value = phone.strip()

    if value.startswith("00"):
        value = f"+{value[2:]}"

    if value.startswith("+"):
        return f"+{re.sub(r'\D', '', value[1:])}"

    return re.sub(r"\D", "", value)


async def find_patient_by_phone(
    clinic_id: UUID,
    phone: str,
) -> dict | None:
    normalized_phone = normalize_phone(phone)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    phone,
                    full_name,
                    email,
                    administrative_notes,
                    active,
                    created_at,
                    updated_at
                FROM patients
                WHERE clinic_id = %s
                  AND phone = %s
                  AND active = TRUE
                LIMIT 1
                """,
                (
                    clinic_id,
                    normalized_phone,
                ),
            )

            return await cur.fetchone()
