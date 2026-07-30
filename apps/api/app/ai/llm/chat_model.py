from typing import Any
from uuid import UUID

from openai import APIError
from pydantic import BaseModel, Field

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)
from app.ai.llm.conversation_interpreter import (
    ConversationInterpretation,
    ConversationInterpretationError,
    interpret_conversation_message,
)


class ChatModelError(RuntimeError):
    """Erreur pendant l'utilisation du modèle conversationnel."""


class ChatReplyContext(BaseModel):
    """Contexte métier utilisé uniquement pour reformuler une réponse."""

    intent: str = Field(
        min_length=1,
        max_length=100,
    )

    user_message: str = Field(
        min_length=1,
        max_length=4000,
    )

    business_reply: str = Field(
        min_length=1,
        max_length=4000,
    )

    conversation_state: str | None = Field(
        default=None,
        max_length=100,
    )

    patient_name: str | None = Field(
        default=None,
        max_length=200,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


CHAT_REPLY_INSTRUCTIONS = """
Tu es l'assistant conversationnel d'un cabinet dentaire.

Ta mission est uniquement de reformuler naturellement une réponse déjà
validée par le moteur métier DentalFlow.

Règles obligatoires :
- Ne change jamais les faits contenus dans la réponse métier.
- N'invente jamais de date, d'heure, de soin, de praticien, de prix,
  de disponibilité ou de rendez-vous.
- Ne confirme jamais une action qui n'est pas confirmée dans la réponse métier.
- Ne donne jamais de diagnostic ni de conseil médical.
- Conserve toutes les informations importantes de la réponse métier.
- Réponds dans la même langue que le patient.
- Utilise un ton professionnel, chaleureux et concis.
- Évite les formulations robotiques et les répétitions.
- Pose au maximum une question lorsque la réponse métier en contient une.
- Retourne uniquement la réponse destinée au patient.
"""


async def interpret_chat_message(
    clinic_id: UUID,
    message: str,
    conversation_context: str | None = None,
) -> ConversationInterpretation:
    """
    Point d'entrée conversationnel pour comprendre un message patient.

    Cette fonction délègue volontairement à l'interpréteur existant afin de
    préserver la logique et les schémas déjà validés.
    """

    return await interpret_conversation_message(
        clinic_id=clinic_id,
        message=message,
        conversation_context=conversation_context,
    )


def _format_reply_input(context: ChatReplyContext) -> str:
    metadata_text = (
        "\n".join(
            f"- {key}: {value}"
            for key, value in context.metadata.items()
            if value is not None
        )
        or "- Aucun"
    )

    return f"""
Message du patient :
{context.user_message}

Intention métier :
{context.intent}

État conversationnel :
{context.conversation_state or "non renseigné"}

Nom du patient :
{context.patient_name or "non renseigné"}

Informations métier complémentaires :
{metadata_text}

Réponse métier validée :
{context.business_reply}

Reformule cette réponse sans modifier son sens.
""".strip()


async def generate_natural_reply(
    context: ChatReplyContext,
) -> str:
    """
    Reformule une réponse métier sans modifier son contenu factuel.

    En cas d'indisponibilité ou d'erreur du LLM, la réponse métier originale
    est retournée afin de ne jamais bloquer le workflow.
    """

    try:
        client = get_openai_client()

        response = await client.responses.create(
            model="gpt-4.1-mini",
            instructions=CHAT_REPLY_INSTRUCTIONS,
            input=_format_reply_input(context),
            max_output_tokens=300,
        )
    except LlmConfigurationError:
        return context.business_reply
    except APIError:
        return context.business_reply

    natural_reply = response.output_text.strip()

    if not natural_reply:
        return context.business_reply

    return natural_reply


__all__ = [
    "ChatModelError",
    "ChatReplyContext",
    "ConversationInterpretation",
    "ConversationInterpretationError",
    "generate_natural_reply",
    "interpret_chat_message",
]
