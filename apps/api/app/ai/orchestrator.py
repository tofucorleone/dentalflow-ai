from typing import Literal

from pydantic import BaseModel

from app.ai.intent import detect_intent
from app.ai.llm.client import LlmConfigurationError
from app.ai.llm.conversation_interpreter import (
    ConversationInterpretation,
    ConversationInterpretationError,
    interpret_conversation_message,
)
from app.ai.schemas import ConversationInput, ConversationIntent
from app.ai.treatment_matcher import find_treatment_in_message


DecisionSource = Literal[
    "dentalflow_rules",
    "treatment_matcher",
    "llm",
    "fallback",
]


class OrchestrationDecision(BaseModel):
    """
    Décision conversationnelle sans exécution métier.

    L'orchestrateur comprend et normalise le message.
    Les handlers DentalFlow restent seuls responsables des actions.
    """

    intent: ConversationIntent
    source: DecisionSource
    confidence: float

    original_message: str
    normalized_message: str

    interpretation: ConversationInterpretation | None = None


def _build_normalized_message(
    interpretation: ConversationInterpretation,
    original_message: str,
) -> str:
    parts = [
        value.strip()
        for value in (
            interpretation.treatment_text,
            interpretation.practitioner_text,
            interpretation.date_text,
            interpretation.time_text,
        )
        if value and value.strip()
    ]

    if not parts:
        return original_message

    return " ".join(parts)


async def orchestrate_conversation_message(
    conversation: ConversationInput,
    conversation_context: str | None = None,
    minimum_confidence: float = 0.75,
) -> OrchestrationDecision:
    """
    Comprend un message avant son passage au moteur métier.

    Priorité :
    1. Les règles DentalFlow gardent la priorité sur l'intention.
    2. Le LLM enrichit le message avec date, heure, soin et praticien.
    3. Si les règles ne comprennent pas, l'intention fiable du LLM est utilisée.
    4. Si le LLM est indisponible, DentalFlow continue sans être bloqué.
    """

    original_message = conversation.message.strip()
    rule_intent = detect_intent(original_message)

    treatment_match = None

    if rule_intent == "unknown":
        treatment_match = await find_treatment_in_message(
            clinic_id=conversation.clinic_id,
            message=original_message,
        )

    interpretation: ConversationInterpretation | None = None

    try:
        interpretation = await interpret_conversation_message(
            clinic_id=conversation.clinic_id,
            message=original_message,
            conversation_context=conversation_context,
        )
    except (
        LlmConfigurationError,
        ConversationInterpretationError,
    ):
        interpretation = None

    if (
        rule_intent == "unknown"
        and treatment_match is not None
        and (
            interpretation is None
            or (
                interpretation.intent == "book_appointment"
                and interpretation.confidence >= minimum_confidence
            )
        )
    ):
        rule_intent = "book_appointment"

    # DentalFlow garde la priorité lorsqu'une règle métier reconnaît l'intention.
    if rule_intent != "unknown":
        normalized_message = original_message

        # On utilise les informations structurées du LLM uniquement
        # lorsqu'elles concernent la même intention métier.
        if (
            interpretation is not None
            and interpretation.intent == rule_intent
            and interpretation.confidence >= minimum_confidence
        ):
            normalized_message = _build_normalized_message(
                interpretation=interpretation,
                original_message=original_message,
            )

        return OrchestrationDecision(
            intent=rule_intent,
            source=(
                "treatment_matcher"
                if treatment_match is not None
                else "dentalflow_rules"
            ),
            confidence=(
                interpretation.confidence
                if interpretation is not None
                and interpretation.intent == rule_intent
                else 1.0
            ),
            original_message=original_message,
            normalized_message=normalized_message,
            interpretation=interpretation,
        )

    # Si DentalFlow n'a rien reconnu, le LLM peut fournir l'intention,
    # mais aucune action métier n'est exécutée ici.
    if (
        interpretation is not None
        and interpretation.intent != "unknown"
        and interpretation.confidence >= minimum_confidence
    ):
        return OrchestrationDecision(
            intent=interpretation.intent,
            source="llm",
            confidence=interpretation.confidence,
            original_message=original_message,
            normalized_message=_build_normalized_message(
                interpretation=interpretation,
                original_message=original_message,
            ),
            interpretation=interpretation,
        )

    return OrchestrationDecision(
        intent="unknown",
        source="fallback",
        confidence=(
            interpretation.confidence
            if interpretation is not None
            else 0.0
        ),
        original_message=original_message,
        normalized_message=original_message,
        interpretation=interpretation,
    )


__all__ = [
    "DecisionSource",
    "OrchestrationDecision",
    "orchestrate_conversation_message",
]
