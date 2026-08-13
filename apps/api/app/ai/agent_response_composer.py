import json
from uuid import UUID

from openai import APIError
from pydantic import BaseModel, Field

from app.ai.agent_tools import AgentToolExecution
from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)


class AgentResponseCompositionError(RuntimeError):
    """Erreur pendant la composition de la réponse agent."""


class AgentComposedReply(BaseModel):
    reply: str = Field(
        min_length=1,
        max_length=2000,
    )


AGENT_RESPONSE_COMPOSER_INSTRUCTIONS = """
Tu rédiges la réponse finale d'un assistant de cabinet dentaire.

Tu reçois :
- le message original du patient ;
- l'intention principale détectée ;
- les résultats réels d'outils métier en lecture seule.

Règles absolues :
- Réponds en français naturel, poli et concis.
- Réponds à toutes les questions du patient dans une seule réponse cohérente.
- Utilise uniquement les données fournies dans les résultats d'outils.
- N'invente jamais de praticien, spécialité, soin, prix, devise, horaire
  ou disponibilité.
- Ne déduis jamais une devise à partir d'un montant numérique.
- Si un prix est fourni sans devise explicite, ne mentionne pas ce prix.
- Utilise le terme "praticiens" pour présenter la liste générale.
- N'utilise "spécialiste" que lorsque la spécialité fournie le justifie
  explicitement.
- Si un outil retourne success=false, explique simplement que l'information
  n'a pas pu être obtenue.
- Si une recherche de disponibilités retourne une liste vide, indique
  clairement qu'aucun créneau n'a été trouvé avec les contraintes demandées.
- Si des créneaux sont présents, propose-les clairement avec la date,
  l'heure et le praticien lorsqu'ils sont disponibles.
- Ne réserve, ne déplace et n'annule jamais de rendez-vous.
- Ne prétends jamais qu'une action a été effectuée.
- Lorsque l'intention principale est book_appointment, termine naturellement
  par une question utile pour poursuivre la réservation.
- Évite les longues introductions et les répétitions.
- Utilise des puces seulement lorsqu'elles rendent la réponse plus claire.
"""


def _serialize_tool_execution(
    execution: AgentToolExecution,
) -> str:
    return json.dumps(
        execution.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        default=str,
    )


async def compose_agent_reply(
    *,
    clinic_id: UUID,
    patient_message: str,
    primary_intent: str,
    execution: AgentToolExecution,
) -> str:
    """
    Compose une réponse naturelle à partir de résultats métier réels.

    clinic_id est conservé dans la signature pour la future
    personnalisation multi-tenant, mais aucune donnée supplémentaire
    n'est chargée ici.
    """

    del clinic_id

    cleaned_message = patient_message.strip()

    if not cleaned_message:
        raise AgentResponseCompositionError(
            "Le message patient est vide."
        )

    client = get_openai_client()

    input_text = (
        "Message original du patient :\n"
        f"{cleaned_message}\n\n"
        "Intention principale :\n"
        f"{primary_intent}\n\n"
        "Résultats réels des outils :\n"
        f"{_serialize_tool_execution(execution)}"
    )

    try:
        response = await client.responses.parse(
            model="gpt-4.1-mini",
            instructions=AGENT_RESPONSE_COMPOSER_INSTRUCTIONS,
            input=input_text,
            text_format=AgentComposedReply,
            max_output_tokens=600,
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise AgentResponseCompositionError(
            "Le service de composition IA est momentanément indisponible."
        ) from exc

    composition = response.output_parsed

    if composition is None:
        raise AgentResponseCompositionError(
            "Le modèle n'a retourné aucune réponse exploitable."
        )

    return composition.reply.strip()


__all__ = [
    "AgentComposedReply",
    "AgentResponseCompositionError",
    "compose_agent_reply",
]
