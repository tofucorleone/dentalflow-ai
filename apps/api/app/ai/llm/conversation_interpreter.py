from typing import Literal
from uuid import UUID

from openai import APIError
from pydantic import BaseModel, Field

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)
from app.ai.schemas import ConversationIntent
from app.practitioner_service import list_practitioners
from app.treatment_service import list_active_treatments


class ConversationInterpretationError(RuntimeError):
    """Erreur pendant l'interprétation conversationnelle par le LLM."""


AgentToolName = Literal[
    "list_practitioners",
    "list_treatments",
    "search_treatments",
    "find_available_slots",
    "clinic_information",
]


class RequestedAgentTool(BaseModel):
    """
    Outil métier demandé par l'analyse conversationnelle.

    Ce modèle décrit uniquement le besoin détecté.
    Il n'exécute aucune action métier.
    """

    name: AgentToolName

    query: str | None = Field(
        default=None,
        max_length=200,
    )

    date_text: str | None = Field(
        default=None,
        max_length=120,
    )

    time_text: str | None = Field(
        default=None,
        max_length=120,
    )

    practitioner_text: str | None = Field(
        default=None,
        max_length=150,
    )

    treatment_text: str | None = Field(
        default=None,
        max_length=120,
    )


class ConversationInterpretation(BaseModel):
    intent: ConversationIntent = "unknown"

    workflow_action: Literal[
        "continue",
        "correct",
        "abandon",
        "switch",
        "none",
    ] = "none"

    treatment_text: str | None = Field(
        default=None,
        max_length=120,
    )
    practitioner_text: str | None = Field(
        default=None,
        max_length=150,
    )
    date_text: str | None = Field(
        default=None,
        max_length=120,
    )
    time_text: str | None = Field(
        default=None,
        max_length=120,
    )

    selected_slot_index: int | None = Field(
        default=None,
        ge=1,
        le=10,
    )

    requested_tools: list[RequestedAgentTool] = Field(
        default_factory=list,
        max_length=8,
    )

    confidence: float = Field(
        ge=0,
        le=1,
    )

    needs_clarification: bool = False

    clarification_field: Literal[
        "intent",
        "treatment",
        "practitioner",
        "date",
        "time",
        "none",
    ] = "none"


CONVERSATION_INTERPRETER_INSTRUCTIONS = """
Tu interprètes les messages reçus par l'assistant d'un cabinet dentaire.

Ta mission est uniquement d'extraire les informations du message.
Tu ne dois jamais réserver, déplacer ou annuler toi-même un rendez-vous.

Intentions autorisées :
- greeting
- thanks
- goodbye
- book_appointment
- reschedule_appointment
- cancel_appointment
- clinic_information
- treatment_pricing
- dental_information
- preference_update
- human_handoff
- unknown

Règles générales :
- workflow_action décrit uniquement la relation du message avec un workflow conversationnel déjà en cours :
  - "continue" : le patient répond normalement à la question du workflow en cours.
  - "correct" : le patient corrige ou remplace une information du workflow en cours.
  - "abandon" : le patient indique qu'il ne souhaite plus poursuivre la demande en cours.
  - "switch" : le patient abandonne implicitement le workflow en cours et formule une autre intention métier.
  - "none" : aucun workflow en cours n'est concerné ou le message ne permet pas de déterminer cette relation.
- N'utilise "abandon", "correct", "continue" ou "switch" que si le contexte conversationnel montre réellement un workflow en cours.
- "Laisse tomber", "oublie", "annule cette demande", "je ne veux plus prendre de rendez-vous" indiquent "abandon" lorsqu'une prise de rendez-vous est en cours.
- Si une prise de rendez-vous est en cours et que le patient explique qu'il a déjà un rendez-vous et ne veut donc pas en prendre un nouveau, utilise "abandon". Cela ne signifie jamais cancel_appointment : le rendez-vous existant ne doit pas être annulé.
- Si le patient change explicitement de demande, par exemple d'une prise de rendez-vous vers l'annulation d'un rendez-vous existant, utilise "switch" avec la nouvelle intention métier.
- Ne fabrique aucune date, heure, personne ou soin.
- Une valeur absente doit être null.
- Si le message est ambigu, baisse confidence.
- needs_clarification doit être true seulement lorsqu'une ambiguïté
  empêche de comprendre une information explicitement demandée.
- clarification_field indique le champ ambigu, sinon "none".
- Une question générale sur les soins, l’hygiène ou les traitements dentaires
  doit utiliser dental_information.
- Lorsqu'un message demande des disponibilités, un créneau ou un rendez-vous,
  l'intention principale doit être book_appointment, même si le même message
  demande aussi la liste des praticiens, des spécialistes, des soins ou des
  informations générales sur le cabinet.
- Exemples utilisant book_appointment :
  "Quels spécialistes avez-vous et quels créneaux sont disponibles cette semaine ?"
  "Faites-vous des implants et avez-vous une place jeudi après 17h ?"
  "Quels médecins avez-vous et puis-je venir demain ?"
- clinic_information doit être utilisé seulement lorsque le patient demande
  des informations sur le cabinet sans demander de disponibilité ni de rendez-vous.
- Un remerciement simple doit utiliser thanks.
- Une formule de fin de conversation comme "au revoir", "bonne journée"
  ou "à bientôt" doit utiliser goodbye.
- Un message qui exprime uniquement une préférence durable du patient
  doit utiliser preference_update.
- Exemples de preference_update :
  "Je préfère toujours le Dr Sara",
  "Le vendredi m'arrange mieux",
  "Je suis disponible seulement après 17h".
- Si le patient exprime une préférence et demande aussi explicitement
  un rendez-vous, conserve book_appointment.
- human_handoff est réservé aux urgences, aux symptômes personnels nécessitant
  un avis clinique, aux demandes de diagnostic et aux demandes explicites
  de parler à une personne.
- Ne donne jamais de diagnostic médical.
- Le moteur métier DentalFlow vérifiera toutes les informations.
- Si le patient choisit un créneau parmi une liste ("le premier",
  "le deuxième", "le 3e"...), renseigne selected_slot_index.
- Si aucun créneau n'est explicitement choisi, retourne null.
- requested_tools décrit les informations métier nécessaires pour répondre
  à toutes les questions présentes dans le message.
- Ne demande jamais un outil inutile.
- Plusieurs outils peuvent être demandés dans un même message.
- Outils autorisés :
  - list_practitioners : lister les médecins, dentistes ou spécialistes.
  - list_treatments : lister les soins proposés par le cabinet.
  - search_treatments : vérifier un soin précis, avec query ou treatment_text.
  - find_available_slots : rechercher des disponibilités, avec les contraintes
    explicites de date, heure, praticien ou soin.
  - clinic_information : répondre sur l'adresse, les horaires ou les
    informations générales du cabinet.
- Exemple :
  "Quels spécialistes avez-vous et avez-vous une place jeudi après 17h ?"
  doit demander list_practitioners et find_available_slots.
- N'invente jamais une contrainte absente du message.
- Les outils décrivent seulement un besoin. Ils ne doivent jamais réserver,
  déplacer ou annuler un rendez-vous.
- Normalise les préférences horaires usuelles :
  - "après le travail" ou "après le boulot" -> "après 17h"
  - "pause déjeuner" ou "à midi" -> "entre 12h et 14h"
  - "en fin de journée" -> "fin de journée"
  - "le plus tôt possible" -> "le plus tôt possible"
- Une date absente peut nécessiter une clarification sans supprimer une
  préférence horaire clairement exprimée.
"""


def _format_clinic_context(
    treatments: list[dict],
    practitioners: list[dict],
) -> str:
    treatment_lines = [
        f"- {treatment['name']}"
        for treatment in treatments
    ]

    practitioner_lines = [
        (
            f"- {practitioner['full_name']}"
            + (
                f" ({practitioner['speciality']})"
                if practitioner.get("speciality")
                else ""
            )
        )
        for practitioner in practitioners
    ]

    treatments_text = (
        "\n".join(treatment_lines)
        if treatment_lines
        else "- Aucun soin configuré"
    )

    practitioners_text = (
        "\n".join(practitioner_lines)
        if practitioner_lines
        else "- Aucun praticien configuré"
    )

    return f"""
Contexte réel du cabinet :

Soins actifs :
{treatments_text}

Praticiens actifs :
{practitioners_text}

Règles de normalisation :
- treatment_text doit être exactement le nom d'un soin actif ci-dessus.
- practitioner_text doit être exactement le nom d'un praticien actif ci-dessus.
- Si la formulation du patient ne correspond pas suffisamment à une valeur
  configurée, retourne null pour ce champ.
- Ne retourne jamais un soin ou un praticien absent de ces listes.
"""


async def interpret_conversation_message(
    clinic_id: UUID,
    message: str,
    conversation_context: str | None = None,
) -> ConversationInterpretation:
    cleaned_message = message.strip()

    if not cleaned_message:
        raise ConversationInterpretationError(
            "Le message à interpréter est vide.",
        )

    treatments = await list_active_treatments(clinic_id)
    practitioners = await list_practitioners(
        clinic_id=clinic_id,
        include_inactive=False,
    )

    clinic_context = _format_clinic_context(
        treatments=treatments,
        practitioners=practitioners,
    )

    client = get_openai_client()

    try:
        response = await client.responses.parse(
            model="gpt-4.1-mini",
            instructions=(
                CONVERSATION_INTERPRETER_INSTRUCTIONS
                + clinic_context
            ),
            input=(
                cleaned_message
                if not conversation_context
                else (
                    f"Contexte conversationnel actuel :\n"
                    f"{conversation_context.strip()}\n\n"
                    f"Message du patient :\n"
                    f"{cleaned_message}"
                )
            ),
            text_format=ConversationInterpretation,
            max_output_tokens=600,
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise ConversationInterpretationError(
            "Le service d'interprétation IA est momentanément indisponible.",
        ) from exc

    interpretation = response.output_parsed

    if interpretation is None:
        raise ConversationInterpretationError(
            "Le modèle n'a retourné aucune interprétation exploitable.",
        )

    if (
        interpretation.intent
        in {
            "book_appointment",
            "reschedule_appointment",
        }
        and interpretation.date_text is None
    ):
        interpretation = interpretation.model_copy(
            update={
                "needs_clarification": True,
                "clarification_field": "date",
            }
        )

    return interpretation


__all__ = [
    "AgentToolName",
    "ConversationInterpretation",
    "ConversationInterpretationError",
    "RequestedAgentTool",
    "interpret_conversation_message",
]
