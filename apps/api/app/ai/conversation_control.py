from typing import Literal
from uuid import UUID


ConversationControlMode = Literal[
    "ai_active",
    "human_active",
    "paused",
    "closed",
]

SUPPORTED_CONTROL_MODES: frozenset[str] = frozenset(
    {
        "ai_active",
        "human_active",
        "paused",
        "closed",
    }
)


def normalize_conversation_sender_phone(
    sender_phone: str,
) -> str:
    normalized = sender_phone.strip()

    if not normalized:
        raise ValueError(
            "Le numéro de l'expéditeur est obligatoire."
        )

    return normalized


def validate_conversation_control_mode(
    mode: str,
) -> ConversationControlMode:
    normalized = mode.strip().lower()

    if normalized not in SUPPORTED_CONTROL_MODES:
        raise ValueError(
            "Mode de conversation invalide."
        )

    return normalized  # type: ignore[return-value]


def automatic_reply_allowed(
    control: dict | None,
) -> bool:
    """
    L'absence de contrôle conserve le comportement historique :
    l'IA reste active.

    Une réponse automatique n'est autorisée que lorsque le mode
    explicite est ai_active.
    """

    if control is None:
        return True

    return control.get("mode") == "ai_active"


async def get_conversation_control(
    *,
    cur,
    clinic_id: UUID,
    channel: str,
    sender_phone: str,
) -> dict | None:
    normalized_phone = normalize_conversation_sender_phone(
        sender_phone
    )

    await cur.execute(
        """
        SELECT
            id,
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            mode,
            taken_over_by_user_id,
            taken_over_at,
            created_at,
            updated_at
        FROM conversation_controls
        WHERE clinic_id = %s
          AND channel = %s
          AND sender_phone = %s
        LIMIT 1
        """,
        (
            clinic_id,
            channel,
            normalized_phone,
        ),
    )

    return await cur.fetchone()


async def set_conversation_mode(
    *,
    cur,
    clinic_id: UUID,
    channel: str,
    sender_phone: str,
    mode: ConversationControlMode,
    patient_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict:
    normalized_phone = normalize_conversation_sender_phone(
        sender_phone
    )
    normalized_mode = validate_conversation_control_mode(
        mode
    )

    if (
        normalized_mode == "human_active"
        and user_id is None
    ):
        raise ValueError(
            "Un utilisateur est requis pour prendre "
            "la main sur une conversation."
        )

    taken_over_by_user_id = (
        user_id
        if normalized_mode == "human_active"
        else None
    )

    await cur.execute(
        """
        INSERT INTO conversation_controls (
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            mode,
            taken_over_by_user_id,
            taken_over_at
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            CASE
                WHEN %s = 'human_active'
                THEN NOW()
                ELSE NULL
            END
        )
        ON CONFLICT (
            clinic_id,
            channel,
            sender_phone
        )
        DO UPDATE SET
            patient_id = COALESCE(
                EXCLUDED.patient_id,
                conversation_controls.patient_id
            ),
            mode = EXCLUDED.mode,
            taken_over_by_user_id =
                EXCLUDED.taken_over_by_user_id,
            taken_over_at = CASE
                WHEN EXCLUDED.mode = 'human_active'
                THEN NOW()
                ELSE NULL
            END,
            updated_at = NOW()
        RETURNING
            id,
            clinic_id,
            patient_id,
            channel,
            sender_phone,
            mode,
            taken_over_by_user_id,
            taken_over_at,
            created_at,
            updated_at
        """,
        (
            clinic_id,
            patient_id,
            channel,
            normalized_phone,
            normalized_mode,
            taken_over_by_user_id,
            normalized_mode,
        ),
    )

    row = await cur.fetchone()

    if row is None:
        raise RuntimeError(
            "Le contrôle de conversation n'a pas "
            "pu être enregistré."
        )

    return row


__all__ = [
    "ConversationControlMode",
    "SUPPORTED_CONTROL_MODES",
    "automatic_reply_allowed",
    "get_conversation_control",
    "normalize_conversation_sender_phone",
    "set_conversation_mode",
    "validate_conversation_control_mode",
]
