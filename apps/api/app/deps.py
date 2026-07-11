from uuid import UUID

from fastapi import Header, HTTPException, status

from app.db import connection


async def clinic_id(
    x_clinic_id: str = Header(..., alias="X-Clinic-Id"),
) -> UUID:
    try:
        parsed = UUID(x_clinic_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Clinic-Id doit être un UUID valide.",
        ) from exc

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM clinics WHERE id = %s AND active = TRUE",
                (parsed,),
            )
            if await cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Clinique introuvable ou inactive.",
                )

    return parsed
