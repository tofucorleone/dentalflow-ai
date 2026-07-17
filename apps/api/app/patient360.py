import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import connection
from app.deps import clinic_id
from app.patient360_schemas import PatientMemoryIn, PatientNoteIn


router = APIRouter(prefix="/patients", tags=["Patient 360"])


async def ensure_patient(cur, current_clinic: UUID, patient_id: UUID) -> dict:
    await cur.execute(
        """
        SELECT id, phone, full_name, email, preferred_practitioner_id,
               administrative_notes, active, created_at, updated_at
        FROM patients
        WHERE clinic_id = %s AND id = %s
        """,
        (current_clinic, patient_id),
    )
    patient = await cur.fetchone()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable.",
        )
    return patient


@router.get("/{patient_id}")
async def get_patient_360(
    patient_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            patient = await ensure_patient(cur, current_clinic, patient_id)

            await cur.execute(
                """
                SELECT
                    a.id, a.status, a.channel, a.start_at, a.end_at,
                    a.google_calendar_event_id, a.notes,
                    pr.full_name AS practitioner_name,
                    t.name AS treatment_name,
                    t.price AS treatment_price
                FROM appointments a
                LEFT JOIN practitioners pr ON pr.id = a.practitioner_id
                LEFT JOIN treatments t ON t.id = a.treatment_id
                WHERE a.clinic_id = %s AND a.patient_id = %s
                ORDER BY a.start_at DESC
                """,
                (current_clinic, patient_id),
            )
            appointments = await cur.fetchall()

            await cur.execute(
                """
                SELECT id, author_name, note, created_at, updated_at
                FROM patient_notes
                WHERE clinic_id = %s AND patient_id = %s
                ORDER BY created_at DESC
                """,
                (current_clinic, patient_id),
            )
            notes = await cur.fetchall()

            await cur.execute(
                """
                SELECT id, document_type, filename, original_filename,
                        storage_url, mime_type, size_bytes, created_at
                FROM patient_documents
                WHERE clinic_id = %s AND patient_id = %s
                ORDER BY created_at DESC
                """,
                (current_clinic, patient_id),
            )
            documents = await cur.fetchall()

            await cur.execute(
                """
                SELECT id, channel, direction, message, external_id, created_at
                FROM conversation_history
                WHERE clinic_id = %s AND patient_id = %s
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (current_clinic, patient_id),
            )
            conversations = await cur.fetchall()

            await cur.execute(
                """
                SELECT summary, preferences, last_goal, updated_at
                FROM patient_ai_memory
                WHERE clinic_id = %s AND patient_id = %s
                """,
                (current_clinic, patient_id),
            )
            memory = await cur.fetchone()

            await cur.execute(
                """
                SELECT id, category, value, is_active, created_at, updated_at
                FROM medical_history
                WHERE clinic_id = %s AND patient_id = %s
                ORDER BY created_at DESC
                """,
                (current_clinic, patient_id),
            )
            medical_history = await cur.fetchall()

    return {
        "patient": patient,
        "appointments": appointments,
        "notes": notes,
        "documents": documents,
        "conversations": conversations,
        "memory": memory,
        "medical_history": medical_history,
    }


@router.post("/{patient_id}/notes", status_code=status.HTTP_201_CREATED)
async def create_note(
    patient_id: UUID,
    payload: PatientNoteIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)
            await cur.execute(
                """
                INSERT INTO patient_notes (
                    clinic_id, patient_id, author_name, note
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id, author_name, note, created_at, updated_at
                """,
                (current_clinic, patient_id, payload.author_name, payload.note),
            )
            note = await cur.fetchone()
            await conn.commit()
            return note


@router.delete(
    "/{patient_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note(
    patient_id: UUID,
    note_id: UUID,
    current_clinic: UUID = Depends(clinic_id),
) -> None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)

            await cur.execute(
                """
                DELETE FROM patient_notes
                WHERE id = %s
                  AND patient_id = %s
                  AND clinic_id = %s
                RETURNING id
                """,
                (
                    note_id,
                    patient_id,
                    current_clinic,
                ),
            )

            deleted_note = await cur.fetchone()

            if deleted_note is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Note introuvable.",
                )

            await conn.commit()


@router.put("/{patient_id}/memory")
async def upsert_memory(
    patient_id: UUID,
    payload: PatientMemoryIn,
    current_clinic: UUID = Depends(clinic_id),
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await ensure_patient(cur, current_clinic, patient_id)
            await cur.execute(
                """
                INSERT INTO patient_ai_memory (
                    patient_id, clinic_id, summary, preferences, last_goal
                )
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (patient_id)
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    preferences = EXCLUDED.preferences,
                    last_goal = EXCLUDED.last_goal,
                    updated_at = NOW()
                RETURNING patient_id, summary, preferences, last_goal, updated_at
                """,
                (
                    patient_id,
                    current_clinic,
                    payload.summary,
                    json.dumps(payload.preferences),
                    payload.last_goal,
                ),
            )
            memory = await cur.fetchone()
            await conn.commit()
            return memory
