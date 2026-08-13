from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.db import connection


async def get_conversation_thread_state(
    *,
    clinic_id: UUID,
    thread_id: UUID,
    session_id: str | None = None,
) -> dict | None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    thread_id,
                    session_id,
                    state,
                    context,
                    last_message_at,
                    created_at,
                    updated_at
                FROM conversation_thread_states
                WHERE clinic_id = %s
                  AND thread_id = %s
                  AND session_id IS NOT DISTINCT FROM %s
                """,
                (
                    clinic_id,
                    thread_id,
                    session_id,
                ),
            )

            return await cur.fetchone()


async def save_conversation_thread_state(
    *,
    clinic_id: UUID,
    thread_id: UUID,
    state: str,
    context: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict:
    if session_id is None:
        conflict_clause = """
            ON CONFLICT (
                clinic_id,
                thread_id
            )
            WHERE session_id IS NULL
        """
    else:
        conflict_clause = """
            ON CONFLICT (
                clinic_id,
                thread_id,
                session_id
            )
            WHERE session_id IS NOT NULL
        """

    query = f"""
        INSERT INTO conversation_thread_states (
            clinic_id,
            thread_id,
            session_id,
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
        {conflict_clause}
        DO UPDATE SET
            state = EXCLUDED.state,
            context = EXCLUDED.context,
            last_message_at = NOW(),
            updated_at = NOW()
        RETURNING
            id,
            clinic_id,
            thread_id,
            session_id,
            state,
            context,
            last_message_at,
            created_at,
            updated_at
    """

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                query,
                (
                    clinic_id,
                    thread_id,
                    session_id,
                    state,
                    Jsonb(context or {}),
                ),
            )

            row = await cur.fetchone()
            await conn.commit()

            if row is None:
                raise RuntimeError(
                    "L'état du fil de conversation n'a pas pu être sauvegardé."
                )

            return row


async def delete_conversation_thread_state(
    *,
    clinic_id: UUID,
    thread_id: UUID,
    session_id: str | None = None,
) -> None:
    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM conversation_thread_states
                WHERE clinic_id = %s
                  AND thread_id = %s
                  AND session_id IS NOT DISTINCT FROM %s
                """,
                (
                    clinic_id,
                    thread_id,
                    session_id,
                ),
            )

            await conn.commit()


__all__ = [
    "delete_conversation_thread_state",
    "get_conversation_thread_state",
    "save_conversation_thread_state",
]
