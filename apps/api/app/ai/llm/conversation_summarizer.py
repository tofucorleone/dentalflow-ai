from openai import APIError
from pydantic import BaseModel, Field

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)


class ConversationSummaryError(RuntimeError):
    """Erreur pendant la synthèse de la mémoire conversationnelle."""


class ConversationSummary(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=2000,
    )

    last_goal: str | None = Field(
        default=None,
        max_length=300,
    )


CONVERSATION_SUMMARY_INSTRUCTIONS = """
Tu résumes l'historique d'un patient avec l'assistant d'un cabinet dentaire.

Ce résumé servira de mémoire conversationnelle durable.

Règles obligatoires :
- Conserve uniquement les informations utiles pour les futures conversations.
- Conserve les demandes importantes, décisions prises et actions réellement
  confirmées.
- Distingue clairement une demande envisagée d'une action confirmée.
- Ne transforme jamais une proposition de créneau en rendez-vous confirmé.
- Ne fabrique aucun soin, praticien, horaire, diagnostic ou rendez-vous.
- Ne conserve pas les salutations, répétitions ou formulations inutiles.
- Ne donne aucun diagnostic médical.
- N'inclus pas d'informations techniques sur le système.
- Le résumé doit être factuel, compact et compréhensible.
- last_goal correspond au dernier objectif conversationnel significatif
  du patient.
- Si aucun objectif significatif n'est identifiable, last_goal doit être null.
"""


def _format_summary_input(
    *,
    history: list[dict[str, str]],
    previous_summary: str | None,
) -> str:
    lines: list[str] = []

    for message in history:
        role = message.get("role")
        content = message.get("content")

        if not isinstance(role, str):
            continue

        if not isinstance(content, str):
            continue

        cleaned_content = content.strip()

        if not cleaned_content:
            continue

        prefix = (
            "Patient"
            if role.lower() == "user"
            else "Assistant"
        )

        lines.append(f"{prefix}: {cleaned_content}")

    history_text = "\n".join(lines) or "Aucun échange exploitable."

    return f"""
Résumé précédent :
{previous_summary or "Aucun résumé précédent."}

Historique récent :
{history_text}

Produis une mémoire mise à jour en intégrant uniquement les informations
fiables et utiles des échanges récents.
""".strip()


async def summarize_conversation_history(
    *,
    history: list[dict[str, str]],
    previous_summary: str | None = None,
) -> ConversationSummary:
    if not history:
        raise ConversationSummaryError(
            "L'historique à résumer est vide.",
        )

    try:
        client = get_openai_client()

        response = await client.responses.parse(
            model="gpt-4.1-mini",
            instructions=CONVERSATION_SUMMARY_INSTRUCTIONS,
            input=_format_summary_input(
                history=history,
                previous_summary=previous_summary,
            ),
            text_format=ConversationSummary,
            max_output_tokens=500,
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise ConversationSummaryError(
            "Le service de synthèse conversationnelle est indisponible.",
        ) from exc

    summary = response.output_parsed

    if summary is None:
        raise ConversationSummaryError(
            "Le modèle n'a retourné aucun résumé exploitable.",
        )

    return summary


__all__ = [
    "ConversationSummary",
    "ConversationSummaryError",
    "summarize_conversation_history",
]
