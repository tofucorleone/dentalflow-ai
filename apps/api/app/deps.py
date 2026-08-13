from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.auth import current_user
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


async def authenticated_clinic_id(
    x_clinic_id: str = Header(..., alias="X-Clinic-Id"),
    user: dict = Depends(current_user),
) -> UUID:
    try:
        requested_clinic_id = UUID(x_clinic_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Clinic-Id doit être un UUID valide.",
        ) from exc

    user_clinic_id = user.get("clinic_id")

    if not isinstance(user_clinic_id, UUID):
        try:
            user_clinic_id = UUID(str(user_clinic_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Contexte clinique utilisateur invalide.",
            ) from exc

    if requested_clinic_id != user_clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit à cette clinique.",
        )

    return user_clinic_id

