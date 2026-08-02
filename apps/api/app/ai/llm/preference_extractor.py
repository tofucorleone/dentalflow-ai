from uuid import UUID

from openai import APIError
from pydantic import BaseModel, Field

from app.ai.llm.client import (
    LlmConfigurationError,
    get_openai_client,
)
from app.practitioner_service import list_practitioners


class PreferenceExtractionError(RuntimeError):
    """Erreur pendant l'extraction des préférences patient."""


class PatientPreferenceExtraction(BaseModel):
    has_preferences: bool = False

    preferred_practitioner: str | None = Field(
        default=None,
        max_length=150,
    )
    preferred_day: str | None = Field(
        default=None,
        max_length=80,
    )
    preferred_time: str | None = Field(
        default=None,
        max_length=120,
    )
    preferred_language: str | None = Field(
        default=None,
        max_length=20,
    )

    confidence: float = Field(
        ge=0,
        le=1,
    )


PREFERENCE_EXTRACTION_INSTRUCTIONS = """
Tu extrais uniquement les préférences durables exprimées explicitement
par un patient d'un cabinet dentaire.

Une préférence durable est une habitude ou un choix récurrent, par exemple :
- "Je préfère toujours le Dr Sara."
- "Le vendredi m'arrange mieux."
- "Je suis disponible seulement après 17h."
- "Je préfère parler en français."

Ne considère pas comme préférence durable :
- une demande ponctuelle ;
- une date précise pour un seul rendez-vous ;
- un horaire demandé uniquement pour aujourd'hui ou demain ;
- un praticien choisi uniquement pour le rendez-vous actuel ;
- une information implicite ou incertaine.

Règles :
- Ne fabrique aucune préférence.
- Une valeur absente doit être null.
- has_preferences doit être true seulement si au moins une préférence
  durable est clairement exprimée.
- preferred_practitioner doit correspondre exactement à un praticien actif
  fourni dans le contexte.
- Ne retourne jamais un praticien absent du contexte.
- Normalise les jours en français et en minuscules :
  lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche.
- Normalise les préférences horaires usuelles :
  - "après le travail" ou "après le boulot" -> "après 17h"
  - "le matin" -> "matin"
  - "l'après-midi" -> "après-midi"
  - "en fin de journée" -> "fin de journée"
- preferred_language utilise un code court :
  fr, ar, en.
- confidence représente la certitude que le patient exprime bien
  une préférence durable.
"""


def _format_practitioner_context(
    practitioners: list[dict],
) -> str:
    lines = [
        f"- {practitioner['full_name']}"
        for practitioner in practitioners
    ]

    practitioners_text = (
        "\n".join(lines)
        if lines
        else "- Aucun praticien actif"
    )

    return f"""
Praticiens actifs du cabinet :
{practitioners_text}
""".strip()


async def extract_patient_preferences(
    clinic_id: UUID,
    message: str,
) -> PatientPreferenceExtraction:
    cleaned_message = message.strip()

    if not cleaned_message:
        raise PreferenceExtractionError(
            "Le message à analyser est vide.",
        )

    practitioners = await list_practitioners(
        clinic_id=clinic_id,
        include_inactive=False,
    )

    practitioner_context = _format_practitioner_context(
        practitioners,
    )

    try:
        client = get_openai_client()

        response = await client.responses.parse(
            model="gpt-4.1-mini",
            instructions=(
                PREFERENCE_EXTRACTION_INSTRUCTIONS
                + "\n\n"
                + practitioner_context
            ),
            input=f"Message du patient :\n{cleaned_message}",
            text_format=PatientPreferenceExtraction,
            max_output_tokens=250,
        )
    except LlmConfigurationError:
        raise
    except APIError as exc:
        raise PreferenceExtractionError(
            "Le service d'extraction des préférences est indisponible.",
        ) from exc

    extraction = response.output_parsed

    if extraction is None:
        raise PreferenceExtractionError(
            "Le modèle n'a retourné aucune extraction exploitable.",
        )

    has_value = any(
        value is not None
        for value in (
            extraction.preferred_practitioner,
            extraction.preferred_day,
            extraction.preferred_time,
            extraction.preferred_language,
        )
    )

    if not has_value:
        return extraction.model_copy(
            update={
                "has_preferences": False,
            },
        )

    return extraction


__all__ = [
    "PatientPreferenceExtraction",
    "PreferenceExtractionError",
    "extract_patient_preferences",
]
