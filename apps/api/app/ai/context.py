from uuid import UUID

from pydantic import BaseModel, Field

from app.db import connection


class PatientContext(BaseModel):
    patient_name: str | None = None
    phone: str | None = None
    summary: str | None = None
    last_goal: str | None = None
    notes: list[str] = Field(default_factory=list)
    medical_history: list[str] = Field(default_factory=list)
    recent_documents: list[str] = Field(default_factory=list)
    recent_conversations: list[str] = Field(default_factory=list)


async def build_patient_context(
    clinic_id: UUID,
    patient_id: UUID,
) -> PatientContext | None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    full_name,
                    phone
                FROM patients
                WHERE id = %s
                  AND clinic_id = %s
                  AND active = TRUE
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )

            patient = await cur.fetchone()

            if patient is None:
                return None

            await cur.execute(
                """
                SELECT
                    summary,
                    last_goal
                FROM patient_ai_memory
                WHERE patient_id = %s
                  AND clinic_id = %s
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )
            memory = await cur.fetchone()

            await cur.execute(
                """
                SELECT
                    author_name,
                    note
                FROM patient_notes
                WHERE patient_id = %s
                  AND clinic_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )
            notes = await cur.fetchall()

            await cur.execute(
                """
                SELECT
                    category,
                    value
                FROM medical_history
                WHERE patient_id = %s
                  AND clinic_id = %s
                  AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )
            medical_history = await cur.fetchall()

            await cur.execute(
                """
                SELECT
                    document_type,
                    original_filename
                FROM patient_documents
                WHERE patient_id = %s
                  AND clinic_id = %s
                ORDER BY created_at DESC
                LIMIT 10
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )
            documents = await cur.fetchall()

            await cur.execute(
                """
                SELECT
                    channel,
                    direction,
                    message
                FROM conversation_history
                WHERE patient_id = %s
                  AND clinic_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )
            conversations = await cur.fetchall()

    return PatientContext(
        patient_name=patient["full_name"],
        phone=patient["phone"],
        summary=memory["summary"] if memory else None,
        last_goal=memory["last_goal"] if memory else None,
        notes=[
            (
                f'{note["author_name"] or "Équipe clinique"} : '
                f'{note["note"]}'
            )
            for note in notes
        ],
        medical_history=[
            f'{item["category"]} : {item["value"]}'
            for item in medical_history
        ],
        recent_documents=[
            (
                f'{document["document_type"]} : '
                f'{document["original_filename"]}'
            )
            for document in documents
        ],
        recent_conversations=[
            (
                f'{conversation["channel"]} '
                f'({conversation["direction"]}) : '
                f'{conversation["message"]}'
            )
            for conversation in conversations
        ],
    )
