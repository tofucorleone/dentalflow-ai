from typing import Any, Literal
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import connection


ConversationState = Literal[
    "idle",
    "waiting_for_patient_name",
    "waiting_for_date",
    "waiting_for_time",
    "waiting_for_reschedule_date",
    "waiting_for_reschedule_time",
    "waiting_for_confirmation",
    "completed",
]


async def get_conversation_state(
    clinic_id: UUID,
    patient_id: UUID,
    channel: str,
) -> dict | None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    patient_id,
                    channel,
                    state,
                    context,
                    last_message_at,
                    updated_at
                FROM conversation_states
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND channel = %s
                """,
                (
                    clinic_id,
                    patient_id,
                    channel,
                ),
            )

            return await cur.fetchone()


async def save_conversation_state(
    clinic_id: UUID,
    patient_id: UUID,
    channel: str,
    state: ConversationState,
    context: dict[str, Any] | None = None,
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO conversation_states (
                    clinic_id,
                    patient_id,
                    channel,
                    state,
                    context,
                    last_message_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (
                    clinic_id,
                    patient_id,
                    channel
                )
                DO UPDATE SET
                    state = EXCLUDED.state,
                    context = EXCLUDED.context,
                    last_message_at = NOW(),
                    updated_at = NOW()
                RETURNING
                    id,
                    clinic_id,
                    patient_id,
                    channel,
                    state,
                    context,
                    last_message_at,
                    updated_at
                """,
                (
                    clinic_id,
                    patient_id,
                    channel,
                    state,
                    Jsonb(context or {}),
                ),
            )

            conversation_state = await cur.fetchone()
            await conn.commit()

            return conversation_state
