from uuid import UUID

from app.db import connection


async def list_practitioners(
    clinic_id: UUID,
    include_inactive: bool = False,
) -> list[dict]:
    query = """
        SELECT
            id,
            clinic_id,
            full_name,
            speciality,
            google_calendar_id,
            phone,
            email,
            active,
            created_at,
            updated_at
        FROM practitioners
        WHERE clinic_id = %s
    """

    if not include_inactive:
        query += " AND active = TRUE"

    query += " ORDER BY full_name"

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (clinic_id,))
            return await cur.fetchall()
