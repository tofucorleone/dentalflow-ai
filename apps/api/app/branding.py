from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth import current_user
from app.db import connection
from app.deps import clinic_id


router = APIRouter(
    prefix="/clinic-branding",
    tags=["Cliniques"],
)

STORAGE_ROOT = Path("/app/storage/branding")
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_LOGO_SIZE = 5 * 1024 * 1024


@router.post(
    "/logo",
    status_code=status.HTTP_201_CREATED,
)
async def upload_clinic_logo(
    file: UploadFile = File(...),
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    del user

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Le logo doit être une image PNG, JPEG ou WebP.",
        )

    content = await file.read()

    if len(content) > MAX_LOGO_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Le logo dépasse la limite de 5 Mo.",
        )

    extension = Path(file.filename or "").suffix.lower()

    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        extension = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }[file.content_type]

    stored_filename = f"logo-{uuid4()}{extension}"
    relative_path = Path(str(current_clinic)) / stored_filename
    absolute_path = STORAGE_ROOT / relative_path

    absolute_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT logo_url
                FROM clinics
                WHERE id = %s
                FOR UPDATE
                """,
                (current_clinic,),
            )

            clinic = await cur.fetchone()

            if clinic is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Clinique introuvable.",
                )

            absolute_path.write_bytes(content)

            await cur.execute(
                """
                UPDATE clinics
                SET
                    logo_url = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING
                    id,
                    logo_url
                """,
                (
                    str(relative_path),
                    current_clinic,
                ),
            )

            updated_clinic = await cur.fetchone()
            await conn.commit()

    previous_logo_url = clinic.get("logo_url")

    if previous_logo_url:
        previous_path = STORAGE_ROOT / previous_logo_url

        if (
            previous_path.exists()
            and previous_path != absolute_path
        ):
            previous_path.unlink()

    return updated_clinic


@router.get("/logo")
async def get_clinic_logo(
    current_clinic: UUID = Depends(clinic_id),
):
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT logo_url
                FROM clinics
                WHERE id = %s
                """,
                (current_clinic,),
            )

            clinic = await cur.fetchone()

            if clinic is None or not clinic["logo_url"]:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Aucun logo configuré.",
                )

    absolute_path = STORAGE_ROOT / clinic["logo_url"]

    if not absolute_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier logo introuvable.",
        )

    return FileResponse(
        path=absolute_path,
    )
