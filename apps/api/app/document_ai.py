from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.document_processing.pdf_extractor import (
    PdfExtractionError,
    extract_pdf_text,
)
from app.ai.document_processing.schemas import (
    ExtractedTextUpdate,
    PdfExtractionResult,
)
from app.ai.llm.client import LlmConfigurationError
from app.ai.llm.document_summarizer import (
    DocumentSummaryError,
    summarize_document,
)
from app.auth import current_user
from app.db import connection
from app.deps import clinic_id


router = APIRouter(
    prefix="/patients",
    tags=["IA documents patients"],
)

STORAGE_ROOT = Path("/app/storage/patients")


@router.post(
    "/{patient_id}/documents/{document_id}/extract",
    response_model=PdfExtractionResult,
)
async def extract_document_text(
    patient_id: UUID,
    document_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> PdfExtractionResult:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    storage_path,
                    mime_type,
                    extracted_text
                FROM patient_documents
                WHERE id = %s
                  AND patient_id = %s
                  AND clinic_id = %s
                """,
                (
                    document_id,
                    patient_id,
                    current_clinic,
                ),
            )

            document = await cur.fetchone()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )

    if document["mime_type"] != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Seuls les documents PDF sont pris en charge pour le moment.",
        )

    file_path = STORAGE_ROOT / document["storage_path"]

    try:
        result = extract_pdf_text(file_path)
    except PdfExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    saved_text = document["extracted_text"]

    if saved_text:
        return result.model_copy(
            update={
                "text": saved_text,
                "character_count": len(saved_text),
                "requires_ocr": False,
            },
        )

    return result

@router.patch(
    "/{patient_id}/documents/{document_id}/extracted-text",
)
async def update_extracted_text(
    patient_id: UUID,
    document_id: UUID,
    payload: ExtractedTextUpdate,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE patient_documents
                SET
                    extracted_text = %s,
                    extraction_status = 'completed',
                    extracted_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                  AND patient_id = %s
                  AND clinic_id = %s
                RETURNING
                    id,
                    extracted_text,
                    extraction_status,
                    extracted_at,
                    updated_at
                """,
                (
                    payload.text,
                    document_id,
                    patient_id,
                    current_clinic,
                ),
            )

            document = await cur.fetchone()

            if document is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document introuvable.",
                )

            await conn.commit()
            return document

@router.post(
    "/{patient_id}/documents/{document_id}/summary",
)
async def summarize_patient_document(
    patient_id: UUID,
    document_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
    user: dict = Depends(current_user),
) -> dict[str, str]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    storage_path,
                    mime_type,
                    extracted_text
                FROM patient_documents
                WHERE id = %s
                  AND patient_id = %s
                  AND clinic_id = %s
                """,
                (
                    document_id,
                    patient_id,
                    current_clinic,
                ),
            )

            document = await cur.fetchone()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document introuvable.",
        )

    source_text = document["extracted_text"]

    if not source_text:
        if document["mime_type"] != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "Seuls les documents PDF sont actuellement "
                    "pris en charge."
                ),
            )

        file_path = STORAGE_ROOT / document["storage_path"]

        try:
            extraction = extract_pdf_text(file_path)
        except PdfExtractionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        source_text = extraction.text

    if not source_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Aucun texte exploitable n'est disponible "
                "pour générer un résumé."
            ),
        )

    try:
        summary = await summarize_document(source_text)
    except LlmConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DocumentSummaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "summary": summary,
    }

