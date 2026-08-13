from uuid import UUID

from app.ai.conversation_control import (
    normalize_conversation_sender_phone,
)


async def get_or_create_conversation_thread(
    *,
    cur,
    clinic_id: UUID,
    channel: str,
    sender_phone: str,
    patient_id: UUID | None = None,
    provider: str | None = None,
    provider_instance: str | None = None,
    external_thread_id: str | None = None,
) -> dict:
    normalized_phone = normalize_conversation_sender_phone(
        sender_phone
    )

    await cur.execute(
        """
        INSERT INTO conversation_threads (
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            provider,
            provider_instance,
            external_thread_id
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            NULLIF(BTRIM(%s), ''),
            NULLIF(BTRIM(%s), ''),
            NULLIF(BTRIM(%s), '')
        )
        ON CONFLICT (
            clinic_id,
            channel,
            sender_phone
        )
        DO UPDATE SET
            patient_id = COALESCE(
                EXCLUDED.patient_id,
                conversation_threads.patient_id
            ),
            provider = COALESCE(
                EXCLUDED.provider,
                conversation_threads.provider
            ),
            provider_instance = COALESCE(
                EXCLUDED.provider_instance,
                conversation_threads.provider_instance
            ),
            external_thread_id = COALESCE(
                EXCLUDED.external_thread_id,
                conversation_threads.external_thread_id
            ),
            updated_at = NOW()
        RETURNING
            id,
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            provider,
            provider_instance,
            external_thread_id,
            assigned_user_id,
            status,
            unread_count,
            last_message_at,
            created_at,
            updated_at
        """,
        (
            clinic_id,
            patient_id,
            channel,
            normalized_phone,
            provider,
            provider_instance,
            external_thread_id,
        ),
    )

    row = await cur.fetchone()

    if row is None:
        raise RuntimeError(
            "Le fil de conversation n'a pas pu être créé."
        )

    return row


async def update_conversation_thread_after_message(
    *,
    cur,
    thread_id: UUID,
    direction: str,
    patient_id: UUID | None = None,
) -> dict:
    if direction not in {"inbound", "outbound"}:
        raise ValueError(
            "La direction doit être inbound ou outbound."
        )

    await cur.execute(
        """
        UPDATE conversation_threads
        SET
            patient_id = COALESCE(
                %s,
                patient_id
            ),
            last_message_at = NOW(),
            unread_count = CASE
                WHEN %s = 'inbound'
                THEN unread_count + 1
                ELSE unread_count
            END,
            updated_at = NOW()
        WHERE id = %s
        RETURNING
            id,
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            provider,
            provider_instance,
            external_thread_id,
            assigned_user_id,
            status,
            unread_count,
            last_message_at,
            created_at,
            updated_at
        """,
        (
            patient_id,
            direction,
            thread_id,
        ),
    )

    row = await cur.fetchone()

    if row is None:
        raise LookupError(
            "Fil de conversation introuvable."
        )

    return row


__all__ = [
    "get_or_create_conversation_thread",
    "update_conversation_thread_after_message",
]
