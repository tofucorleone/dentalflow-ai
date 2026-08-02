from contextvars import ContextVar, Token
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


_current_session_id: ContextVar[str | None] = ContextVar(
    "dentalflow_conversation_session_id",
    default=None,
)


def set_conversation_session(
    session_id: str | None,
) -> Token:
    """
    Active la session conversationnelle pour la tâche asynchrone courante.
    """

    return _current_session_id.set(session_id)


def reset_conversation_session(
    token: Token,
) -> None:
    """
    Restaure la session précédente à la fin du traitement.
    """

    _current_session_id.reset(token)


def _resolve_session_id(
    session_id: str | None,
) -> str | None:
    if session_id is not None:
        return session_id

    return _current_session_id.get()


async def get_conversation_state(
    clinic_id: UUID,
    patient_id: UUID,
    channel: str,
    session_id: str | None = None,
) -> dict | None:
    session_id = _resolve_session_id(session_id)

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    id,
                    clinic_id,
                    patient_id,
                    channel,
                    session_id,
                    state,
                    context,
                    last_message_at,
                    updated_at
                FROM conversation_states
                WHERE clinic_id = %s
                  AND patient_id = %s
                  AND channel = %s
                  AND session_id IS NOT DISTINCT FROM %s
                """,
                (
                    clinic_id,
                    patient_id,
                    channel,
                    session_id,
                ),
            )

            return await cur.fetchone()


async def save_conversation_state(
    clinic_id: UUID,
    patient_id: UUID,
    channel: str,
    state: ConversationState,
    context: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict:
    session_id = _resolve_session_id(session_id)

    if session_id is None:
        conflict_clause = """
            ON CONFLICT (
                clinic_id,
                patient_id,
                channel
            )
            WHERE session_id IS NULL
        """
    else:
        conflict_clause = """
            ON CONFLICT (
                clinic_id,
                patient_id,
                channel,
                session_id
            )
            WHERE session_id IS NOT NULL
        """

    query = f"""
        INSERT INTO conversation_states (
            clinic_id,
            patient_id,
            channel,
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
            patient_id,
            channel,
            session_id,
            state,
            context,
            last_message_at,
            updated_at
    """

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                query,
                (
                    clinic_id,
                    patient_id,
                    channel,
                    session_id,
                    state,
                    Jsonb(context or {}),
                ),
            )

            conversation_state = await cur.fetchone()
            await conn.commit()

            return conversation_state


async def append_conversation_turn(
    clinic_id: UUID,
    patient_id: UUID,
    channel: str,
    user_message: str,
    assistant_message: str,
    max_messages: int = 20,
    session_id: str | None = None,
) -> dict | None:
    """
    Ajoute atomiquement un tour utilisateur/assistant à context["history"].

    Cette fonction ne modifie ni l'état métier ni les autres clés du contexte.
    Elle conserve uniquement les derniers messages définis par max_messages.
    """

    session_id = _resolve_session_id(session_id)

    messages = [
        {
            "role": "user",
            "content": user_message.strip(),
        },
        {
            "role": "assistant",
            "content": assistant_message.strip(),
        },
    ]

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                WITH current_history AS (
                    SELECT
                        id,
                        CASE
                            WHEN jsonb_typeof(context -> 'history') = 'array'
                                THEN context -> 'history'
                            ELSE '[]'::jsonb
                        END || %s AS combined_history
                    FROM conversation_states
                    WHERE clinic_id = %s
                      AND patient_id = %s
                      AND channel = %s
                      AND session_id IS NOT DISTINCT FROM %s
                    FOR UPDATE
                ),
                trimmed_history AS (
                    SELECT
                        current_history.id,
                        COALESCE(
                            jsonb_agg(
                                history_item.value
                                ORDER BY history_item.ordinality
                            ) FILTER (
                                WHERE history_item.ordinality > GREATEST(
                                    jsonb_array_length(
                                        current_history.combined_history
                                    ) - %s,
                                    0
                                )
                            ),
                            '[]'::jsonb
                        ) AS history
                    FROM current_history
                    CROSS JOIN LATERAL jsonb_array_elements(
                        current_history.combined_history
                    ) WITH ORDINALITY AS history_item(value, ordinality)
                    GROUP BY
                        current_history.id,
                        current_history.combined_history
                )
                UPDATE conversation_states AS conversation_state
                SET
                    context = jsonb_set(
                        conversation_state.context,
                        '{history}',
                        trimmed_history.history,
                        TRUE
                    ),
                    last_message_at = NOW(),
                    updated_at = NOW()
                FROM trimmed_history
                WHERE conversation_state.id = trimmed_history.id
                RETURNING
                    conversation_state.id,
                    conversation_state.clinic_id,
                    conversation_state.patient_id,
                    conversation_state.channel,
                    conversation_state.session_id,
                    conversation_state.state,
                    conversation_state.context,
                    conversation_state.last_message_at,
                    conversation_state.updated_at
                """,
                (
                    Jsonb(messages),
                    clinic_id,
                    patient_id,
                    channel,
                    session_id,
                    max_messages,
                ),
            )

            updated_state = await cur.fetchone()
            await conn.commit()

            return updated_state

