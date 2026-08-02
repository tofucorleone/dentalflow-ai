from openai import APIError

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)


KNOWLEDGE_FALLBACK_INSTRUCTIONS = """
Tu es l'assistant conversationnel d'un cabinet dentaire.

Tu interviens uniquement lorsque le moteur métier DentalFlow ne sait pas
traiter directement le message du patient.

Règles obligatoires :
- Réponds dans la même langue que le patient.
- Utilise un ton professionnel, chaleureux, naturel et concis.
- Tu peux donner des informations générales sur les soins dentaires.
- Ne donne jamais de diagnostic personnalisé.
- Ne remplace jamais l'avis d'un dentiste.
- Ne prescris jamais de médicament ni de dosage.
- N'invente jamais les horaires, tarifs, praticiens, disponibilités,
  coordonnées ou services du cabinet.
- Ne confirme, ne crée, ne déplace et n'annule jamais de rendez-vous.
- Si le patient demande une action liée à un rendez-vous, invite-le
  simplement à préciser sa demande afin que DentalFlow puisse la traiter.
- Si le message évoque une urgence médicale, une douleur intense,
  un traumatisme, un gonflement important, des difficultés respiratoires
  ou un saignement incontrôlé, recommande de contacter immédiatement
  le cabinet ou les services d'urgence appropriés.
- Lorsque la réponse dépend d'un examen clinique, indique-le clairement.
- Retourne uniquement la réponse destinée au patient.
"""


async def generate_knowledge_fallback(
    user_message: str,
    conversation_context: str | None = None,
) -> str | None:
    """
    Produit une réponse générale sans effectuer d'action métier.

    Retourne None si le modèle est indisponible afin de conserver
    le fallback déterministe de DentalFlow.
    """
    cleaned_message = user_message.strip()

    if not cleaned_message:
        return None

    prompt = (
        f"Contexte conversationnel :\n{conversation_context.strip()}\n\n"
        if conversation_context
        else ""
    )

    prompt += f"Message du patient :\n{cleaned_message}"

    try:
        client = get_openai_client()

        response = await client.responses.create(
            model="gpt-4.1-mini",
            instructions=KNOWLEDGE_FALLBACK_INSTRUCTIONS,
            input=prompt,
            max_output_tokens=350,
        )
    except (
        LlmConfigurationError,
        APIError,
    ):
        return None

    reply = response.output_text.strip()

    return reply or None


__all__ = [
    "generate_knowledge_fallback",
]
