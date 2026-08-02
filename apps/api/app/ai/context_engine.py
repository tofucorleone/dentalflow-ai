from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import connection


async def get_patient_preferences(
    clinic_id: UUID,
    patient_id: UUID,
) -> dict[str, Any]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT preferences
                FROM patient_ai_memory
                WHERE patient_id = %s
                  AND clinic_id = %s
                """,
                (
                    patient_id,
                    clinic_id,
                ),
            )

            row = await cur.fetchone()

    if row is None:
        return {}

    preferences = row.get("preferences")

    return preferences if isinstance(preferences, dict) else {}


async def save_patient_preferences(
    clinic_id: UUID,
    patient_id: UUID,
    preferences: dict[str, Any],
) -> dict[str, Any]:
    cleaned_preferences = {
        key: value
        for key, value in preferences.items()
        if value is not None
    }

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO patient_ai_memory (
                    patient_id,
                    clinic_id,
                    preferences,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (patient_id)
                DO UPDATE SET
                    clinic_id = EXCLUDED.clinic_id,
                    preferences =
                        patient_ai_memory.preferences
                        || EXCLUDED.preferences,
                    updated_at = NOW()
                RETURNING preferences
                """,
                (
                    patient_id,
                    clinic_id,
                    Jsonb(cleaned_preferences),
                ),
            )

            row = await cur.fetchone()
            await conn.commit()

    stored_preferences = row.get("preferences") if row else {}

    return (
        stored_preferences
        if isinstance(stored_preferences, dict)
        else {}
    )


async def save_patient_conversation_summary(
    clinic_id: UUID,
    patient_id: UUID,
    summary: str,
    last_goal: str | None = None,
) -> dict[str, Any]:
    cleaned_summary = summary.strip()

    if not cleaned_summary:
        raise ValueError(
            "Le résumé conversationnel ne peut pas être vide."
        )

    cleaned_last_goal = (
        last_goal.strip()
        if last_goal and last_goal.strip()
        else None
    )

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO patient_ai_memory (
                    patient_id,
                    clinic_id,
                    summary,
                    last_goal,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (patient_id)
                DO UPDATE SET
                    clinic_id = EXCLUDED.clinic_id,
                    summary = EXCLUDED.summary,
                    last_goal = EXCLUDED.last_goal,
                    updated_at = NOW()
                RETURNING
                    summary,
                    last_goal,
                    updated_at
                """,
                (
                    patient_id,
                    clinic_id,
                    cleaned_summary,
                    cleaned_last_goal,
                ),
            )

            row = await cur.fetchone()
            await conn.commit()

    return dict(row) if row else {}


async def delete_patient_preference(
    clinic_id: UUID,
    patient_id: UUID,
    preference_key: str,
) -> dict[str, Any]:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE patient_ai_memory
                SET
                    preferences = preferences - %s,
                    updated_at = NOW()
                WHERE patient_id = %s
                  AND clinic_id = %s
                RETURNING preferences
                """,
                (
                    preference_key,
                    patient_id,
                    clinic_id,
                ),
            )

            row = await cur.fetchone()
            await conn.commit()

    if row is None:
        return {}

    preferences = row.get("preferences")

    return preferences if isinstance(preferences, dict) else {}


__all__ = [
    "delete_patient_preference",
    "get_patient_preferences",
    "save_patient_conversation_summary",
    "save_patient_preferences",
]
