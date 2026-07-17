from uuid import UUID

from app.db import connection


async def list_active_treatments(
    clinic_id: UUID,
) -> list[dict]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    name,
                    description,
                    duration_minutes,
                    price,
                    requires_consultation,
                    active,
                    created_at,
                    updated_at
                FROM treatments
                WHERE clinic_id = %s
                  AND active = TRUE
                ORDER BY name
                """,
                (clinic_id,),
            )

            return await cur.fetchall()
