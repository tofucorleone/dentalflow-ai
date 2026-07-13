from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth import current_user
from app.db import connection
from app.deps import clinic_id


router = APIRouter(
    prefix="/patients",
    tags=["Documents patients"],
)

STORAGE_ROOT = Path("/app/storage/patients")
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_FILE_SIZE = 15 * 1024 * 1024


async def ensure_patient(
    cur,
    current_clinic: UUID,
    patient_id: UUID,
) -> None:
    await cur.execute(
        """
        SELECT id
        FROM patients
        WHERE id = %s
          AND clinic_id = %s
        """,
        (patient_id, current_clinic),
    )

    if await cur.fetchone() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable.",
        )


@router.get("/{patient_id}/documents")
async def list_documents(
    patient_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> list[dict]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)

            await cur.execute(
                """
                SELECT
                    id,
                    document_type,
                    filename,
                    original_filename,
                    mime_type,
                    size_bytes,
                    created_at,
                    updated_at
                FROM patient_documents
                WHERE clinic_id = %s
                  AND patient_id = %s
                ORDER BY created_at DESC
                """,
                (current_clinic, patient_id),
            )

            return await cur.fetchall()


@router.post(
    "/{patient_id}/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    patient_id: UUID,
    document_type: str = Form("other"),
    file: UploadFile = File(...),
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Format de fichier non autorisé.",
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Le fichier dépasse la limite de 15 Mo.",
        )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)

            extension = Path(file.filename or "").suffix.lower()
            stored_filename = f"{uuid4()}{extension}"

            relative_path = (
                Path(str(current_clinic))
                / str(patient_id)
                / stored_filename
            )

            absolute_path = STORAGE_ROOT / relative_path
            absolute_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            absolute_path.write_bytes(content)

            await cur.execute(
                """
                INSERT INTO patient_documents (
                    clinic_id,
                    patient_id,
                    document_type,
                    filename,
                    original_filename,
                    storage_url,
                    storage_path,
                    mime_type,
                    size_bytes,
                    uploaded_by
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING
                    id,
                    document_type,
                    filename,
                    original_filename,
                    mime_type,
                    size_bytes,
                    created_at,
                    updated_at
                """,
                (
                    current_clinic,
                    patient_id,
                    document_type,
                    stored_filename,
                    file.filename or stored_filename,
                    str(relative_path),
                    str(relative_path),
                    file.content_type,
                    len(content),
                    user["id"],
                ),
            )

            document = await cur.fetchone()
            await conn.commit()

            return document


@router.get(
    "/{patient_id}/documents/{document_id}/download",
)
async def download_document(
    patient_id: UUID,
    document_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
):
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)

            await cur.execute(
                """
                SELECT
                    original_filename,
                    storage_path,
                    mime_type
                FROM patient_documents
                WHERE id = %s
                  AND clinic_id = %s
                  AND patient_id = %s
                """,
                (
                    document_id,
                    current_clinic,
                    patient_id,
                ),
            )

            document = await cur.fetchone()

            if document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document introuvable.",
                )

    absolute_path = STORAGE_ROOT / document["storage_path"]

    if not absolute_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier introuvable sur le stockage.",
        )

    return FileResponse(
        path=absolute_path,
        filename=document["original_filename"],
        media_type=document["mime_type"],
    )


@router.delete(
    "/{patient_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    patient_id: UUID,
    document_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)

            await cur.execute(
                """
                SELECT storage_path
                FROM patient_documents
                WHERE id = %s
                  AND clinic_id = %s
                  AND patient_id = %s
                FOR UPDATE
                """,
                (
                    document_id,
                    current_clinic,
                    patient_id,
                ),
            )

            document = await cur.fetchone()

            if document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document introuvable.",
                )

            await cur.execute(
                """
                DELETE FROM patient_documents
                WHERE id = %s
                """,
                (document_id,),
            )

            await conn.commit()

    absolute_path = STORAGE_ROOT / document["storage_path"]

    if absolute_path.exists():
        absolute_path.unlink()

