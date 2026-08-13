from datetime import datetime
from typing import Literal
from uuid import UUID

from psycopg.types.json import Jsonb


ConversationMessageDirection = Literal[
    "inbound",
    "outbound",
]

ConversationMessageAuthorType = Literal[
    "patient",
    "ai",
    "human",
    "system",
]

ConversationMessageType = Literal[
    "text",
    "image",
    "audio",
    "video",
    "document",
    "location",
    "system",
]

ConversationMessageStatus = Literal[
    "received",
    "prepared",
    "sent",
    "delivered",
    "read",
    "failed",
]


VALID_DIRECTIONS: frozenset[str] = frozenset(
    {
        "inbound",
        "outbound",
    }
)

VALID_AUTHOR_TYPES: frozenset[str] = frozenset(
    {
        "patient",
        "ai",
        "human",
        "system",
    }
)

VALID_MESSAGE_TYPES: frozenset[str] = frozenset(
    {
        "text",
        "image",
        "audio",
        "video",
        "document",
        "location",
        "system",
    }
)

VALID_MESSAGE_STATUSES: frozenset[str] = frozenset(
    {
        "received",
        "prepared",
        "sent",
        "delivered",
        "read",
        "failed",
    }
)


def normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()

    return normalized or None


def validate_message_direction(
    direction: str,
) -> ConversationMessageDirection:
    normalized = direction.strip().lower()

    if normalized not in VALID_DIRECTIONS:
        raise ValueError(
            "Direction de message invalide."
        )

    return normalized  # type: ignore[return-value]


def validate_message_author_type(
    author_type: str,
) -> ConversationMessageAuthorType:
    normalized = author_type.strip().lower()

    if normalized not in VALID_AUTHOR_TYPES:
        raise ValueError(
            "Type d'auteur de message invalide."
        )

    return normalized  # type: ignore[return-value]


def validate_message_type(
    message_type: str,
) -> ConversationMessageType:
    normalized = message_type.strip().lower()

    if normalized not in VALID_MESSAGE_TYPES:
        raise ValueError(
            "Type de message invalide."
        )

    return normalized  # type: ignore[return-value]


def validate_message_status(
    status: str,
) -> ConversationMessageStatus:
    normalized = status.strip().lower()

    if normalized not in VALID_MESSAGE_STATUSES:
        raise ValueError(
            "Statut de message invalide."
        )

    return normalized  # type: ignore[return-value]


def validate_message_consistency(
    *,
    direction: ConversationMessageDirection,
    author_type: ConversationMessageAuthorType,
    sent_by_user_id: UUID | None,
) -> None:
    if (
        direction == "inbound"
        and author_type not in {
            "patient",
            "system",
        }
    ):
        raise ValueError(
            "Un message entrant doit provenir "
            "du patient ou du système."
        )

    if (
        direction == "outbound"
        and author_type not in {
            "ai",
            "human",
            "system",
        }
    ):
        raise ValueError(
            "Un message sortant doit provenir "
            "de l'IA, d'un humain ou du système."
        )

    if (
        author_type == "human"
        and sent_by_user_id is None
    ):
        raise ValueError(
            "Un utilisateur est requis pour "
            "un message envoyé par un humain."
        )

    if (
        author_type != "human"
        and sent_by_user_id is not None
    ):
        raise ValueError(
            "sent_by_user_id est réservé "
            "aux messages humains."
        )


async def create_conversation_message(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
    channel: str,
    direction: ConversationMessageDirection,
    author_type: ConversationMessageAuthorType,
    body: str | None,
    patient_id: UUID | None = None,
    sent_by_user_id: UUID | None = None,
    message_type: ConversationMessageType = "text",
    external_id: str | None = None,
    provider: str | None = None,
    status: ConversationMessageStatus = "received",
    requires_validation: bool = False,
    metadata: dict | None = None,
    occurred_at: datetime | None = None,
) -> dict:
    normalized_direction = validate_message_direction(
        direction
    )
    normalized_author_type = validate_message_author_type(
        author_type
    )
    normalized_message_type = validate_message_type(
        message_type
    )
    normalized_status = validate_message_status(
        status
    )

    validate_message_consistency(
        direction=normalized_direction,
        author_type=normalized_author_type,
        sent_by_user_id=sent_by_user_id,
    )

    normalized_body = normalize_optional_text(body)

    if (
        normalized_message_type == "text"
        and normalized_body is None
    ):
        raise ValueError(
            "Le contenu d'un message texte "
            "est obligatoire."
        )

    await cur.execute(
        """
        INSERT INTO conversation_messages (
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            direction,
            author_type,
            message_type,
            body,
            external_id,
            provider,
            status,
            requires_validation,
            metadata,
            occurred_at
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
            NULLIF(BTRIM(%s), ''),
            NULLIF(BTRIM(%s), ''),
            %s,
            %s,
            %s,
            COALESCE(%s, NOW())
        )
        ON CONFLICT (
            clinic_id,
            provider,
            external_id
        )
        WHERE
            provider IS NOT NULL
            AND external_id IS NOT NULL
        DO NOTHING
        RETURNING
            id,
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            direction,
            author_type,
            message_type,
            body,
            external_id,
            provider,
            status,
            requires_validation,
            metadata,
            occurred_at,
            created_at,
            updated_at,
            TRUE AS created
        """,
        (
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            normalized_direction,
            normalized_author_type,
            normalized_message_type,
            normalized_body,
            external_id,
            provider,
            normalized_status,
            requires_validation,
            Jsonb(metadata or {}),
            occurred_at,
        ),
    )

    row = await cur.fetchone()

    if row is not None:
        return row

    normalized_provider = normalize_optional_text(provider)
    normalized_external_id = normalize_optional_text(
        external_id
    )

    if (
        normalized_provider is None
        or normalized_external_id is None
    ):
        raise RuntimeError(
            "Le message n'a pas pu être créé."
        )

    await cur.execute(
        """
        SELECT
            id,
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            direction,
            author_type,
            message_type,
            body,
            external_id,
            provider,
            status,
            requires_validation,
            metadata,
            occurred_at,
            created_at,
            updated_at,
            FALSE AS created
        FROM conversation_messages
        WHERE clinic_id = %s
          AND provider = %s
          AND external_id = %s
        LIMIT 1
        """,
        (
            clinic_id,
            normalized_provider,
            normalized_external_id,
        ),
    )

    existing = await cur.fetchone()

    if existing is None:
        raise RuntimeError(
            "Le message n'a pas pu être créé "
            "ou retrouvé."
        )

    return existing


async def update_conversation_message_status(
    *,
    cur,
    clinic_id: UUID,
    message_id: UUID,
    status: ConversationMessageStatus,
    external_id: str | None = None,
    metadata_patch: dict | None = None,
) -> dict:
    normalized_status = validate_message_status(status)

    await cur.execute(
        """
        UPDATE conversation_messages
        SET
            status = %s,
            external_id = COALESCE(
                NULLIF(BTRIM(%s), ''),
                external_id
            ),
            metadata = metadata || %s,
            updated_at = NOW()
        WHERE id = %s
          AND clinic_id = %s
        RETURNING
            id,
            clinic_id,
            thread_id,
            patient_id,
            sent_by_user_id,
            channel,
            direction,
            author_type,
            message_type,
            body,
            external_id,
            provider,
            status,
            requires_validation,
            metadata,
            occurred_at,
            created_at,
            updated_at
        """,
        (
            normalized_status,
            external_id,
            Jsonb(metadata_patch or {}),
            message_id,
            clinic_id,
        ),
    )

    row = await cur.fetchone()

    if row is None:
        raise LookupError(
            "Message de conversation introuvable."
        )

    return row


__all__ = [
    "ConversationMessageAuthorType",
    "ConversationMessageDirection",
    "ConversationMessageStatus",
    "ConversationMessageType",
    "create_conversation_message",
    "normalize_optional_text",
    "update_conversation_message_status",
    "validate_message_author_type",
    "validate_message_consistency",
    "validate_message_direction",
    "validate_message_status",
    "validate_message_type",
]
