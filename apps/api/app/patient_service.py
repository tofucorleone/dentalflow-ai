from uuid import UUID

from app.ai.patient_matcher import normalize_phone
from app.db import connection


async def upsert_patient_record(
    clinic_id: UUID,
    phone: str,
    full_name: str | None = None,
    email: str | None = None,
    administrative_notes: str | None = None,
) -> dict:
    normalized_phone = normalize_phone(phone)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO patients (
                    clinic_id,
                    phone,
                    full_name,
                    email,
                    administrative_notes
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (clinic_id, phone)
                DO UPDATE SET
                    full_name = COALESCE(
                        EXCLUDED.full_name,
                        patients.full_name
                    ),
                    email = COALESCE(
                        EXCLUDED.email,
                        patients.email
                    ),
                    administrative_notes = COALESCE(
                        EXCLUDED.administrative_notes,
                        patients.administrative_notes
                    ),
                    active = TRUE,
                    updated_at = NOW()
                RETURNING
                    id,
                    clinic_id,
                    phone,
                    full_name,
                    email,
                    administrative_notes,
                    active,
                    created_at,
                    updated_at
                """,
                (
                    clinic_id,
                    normalized_phone,
                    full_name,
                    email,
                    administrative_notes,
                ),
            )

            patient = await cur.fetchone()
            await conn.commit()

            return patient


async def update_patient_name(
    clinic_id: UUID,
    patient_id: UUID,
    full_name: str,
) -> dict | None:
    cleaned_name = " ".join(full_name.strip().split())

    if len(cleaned_name) < 2:
        return None

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE patients
                SET
                    full_name = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND clinic_id = %s
                  AND active = TRUE
                RETURNING
                    id,
                    clinic_id,
                    phone,
                    full_name,
                    email,
                    administrative_notes,
                    active,
                    created_at,
                    updated_at
                """,
                (
                    cleaned_name,
                    patient_id,
                    clinic_id,
                ),
            )

            patient = await cur.fetchone()
            await conn.commit()

            return patient
