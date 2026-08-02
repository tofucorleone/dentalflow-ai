from app.ai.context import build_patient_context
from app.ai.conversation_corrections import is_correction_message
from app.ai.conversation_state import (
    append_conversation_turn,
    get_conversation_state,
    save_conversation_state,
)
from app.ai.handlers.booking import (
    handle_booking,
    handle_booking_confirmation_response,
    handle_booking_date_response,
    handle_booking_time_response,
)
from app.ai.handlers.cancellation import (
    handle_cancellation,
    handle_cancellation_confirmation,
)
from app.ai.handlers.rescheduling import (
    handle_rescheduling,
    handle_rescheduling_confirmation,
    handle_rescheduling_date_response,
    handle_rescheduling_time_response,
)
from app.ai.handlers.greeting import handle_greeting
from app.ai.handlers.treatment_pricing import handle_treatment_pricing
from app.ai.message_parser import extract_message_parts
from app.ai.llm.client import LlmConfigurationError
from app.ai.llm.chat_model import (
    ChatReplyContext,
    generate_natural_reply,
)
from app.ai.llm.history_formatter import format_history_for_llm
from app.ai.llm.knowledge_fallback import generate_knowledge_fallback
from app.ai.llm.conversation_interpreter import (
    ConversationInterpretationError,
    interpret_conversation_message,
)
from app.ai.orchestrator import orchestrate_conversation_message
from app.ai.patient_matcher import find_patient_by_phone
from app.patient_service import (
    update_patient_name,
    upsert_patient_record,
)
from app.ai.schemas import (
    ConversationInput,
    ConversationResult,
)


def _format_patient_preferences(
    preferences: dict,
) -> str | None:
    if not preferences:
        return None

    lines = [
        f"- {key}: {value}"
        for key, value in preferences.items()
        if value is not None
    ]

    if not lines:
        return None

    return (
        "Préférences mémorisées du patient :\n"
        + "\n".join(lines)
        + "\n\n"
        + (
            "Ces préférences sont uniquement un contexte. "
            "Ne les considère jamais comme une demande explicite "
            "du patient dans le message actuel."
        )
    )


def _apply_habitual_preferences(
    *,
    original_message: str,
    routed_message: str,
    preferences: dict,
    interpretation,
) -> str:
    """
    Applique les préférences mémorisées uniquement lorsque le patient
    demande explicitement son fonctionnement habituel.

    Les informations exprimées dans le message actuel restent prioritaires.
    """
    normalized = original_message.strip().lower()

    habitual_markers = (
        "comme d'habitude",
        "comme d’habitude",
        "comme la dernière fois",
        "comme la derniere fois",
        "mes préférences habituelles",
        "mes preferences habituelles",
        "habituellement",
    )

    if not any(marker in normalized for marker in habitual_markers):
        return routed_message

    parts = [
        routed_message.strip(),
    ]

    practitioner_is_missing = (
        interpretation is None
        or interpretation.practitioner_text is None
    )
    date_is_missing = (
        interpretation is None
        or interpretation.date_text is None
    )
    time_is_missing = (
        interpretation is None
        or interpretation.time_text is None
    )

    preferred_practitioner = preferences.get(
        "preferred_practitioner",
    )
    preferred_day = preferences.get("preferred_day")
    preferred_time = preferences.get("preferred_time")

    if practitioner_is_missing and preferred_practitioner:
        parts.append(str(preferred_practitioner))

    if date_is_missing and preferred_day:
        parts.append(str(preferred_day))

    if time_is_missing and preferred_time:
        parts.append(str(preferred_time))

    return " ".join(
        part
        for part in parts
        if part
    )


def _build_interpreted_message(
    treatment_text: str | None,
    practitioner_text: str | None,
    date_text: str | None,
    time_text: str | None,
) -> str:
    parts = [
        value.strip()
        for value in (
            treatment_text,
            practitioner_text,
            date_text,
            time_text,
        )
        if value and value.strip()
    ]

    return " ".join(parts)


async def _process_with_llm_fallback(
    conversation: ConversationInput,
    patient: dict,
    patient_id,
    conversation_context: str | None = None,
) -> ConversationResult | None:
    try:
        interpretation = await interpret_conversation_message(
            clinic_id=conversation.clinic_id,
            message=conversation.message,
            conversation_context=conversation_context,
        )
    except (
        LlmConfigurationError,
        ConversationInterpretationError,
    ):
        return None

    if (
        interpretation.confidence < 0.75
        or interpretation.intent == "unknown"
    ):
        return None

    interpreted_message = _build_interpreted_message(
        treatment_text=interpretation.treatment_text,
        practitioner_text=interpretation.practitioner_text,
        date_text=interpretation.date_text,
        time_text=interpretation.time_text,
    )

    if interpretation.intent == "book_appointment":
        return await handle_booking(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=interpreted_message,
        )

    if interpretation.intent == "reschedule_appointment":
        return await handle_rescheduling(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=interpreted_message,
        )

    if interpretation.intent == "cancel_appointment":
        return await handle_cancellation(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
        )

    if interpretation.intent == "treatment_pricing":
        return await handle_treatment_pricing(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
        )

    if interpretation.intent == "greeting":
        return handle_greeting(patient)

    if interpretation.intent == "clinic_information":
        return ConversationResult(
            intent="clinic_information",
            patient_id=patient_id,
            reply=(
                "Je peux vous renseigner sur les horaires, "
                "l'adresse ou les informations de la clinique."
            ),
        )

    if interpretation.intent == "human_handoff":
        return ConversationResult(
            intent="human_handoff",
            patient_id=patient_id,
            requires_human=True,
            reply=(
                "Votre demande nécessite l'aide de l'équipe du cabinet. "
                "Je vais vous orienter vers une personne."
            ),
        )

    return None


def _has_new_explicit_intent(intent: str) -> bool:
    interruptible_intents = {
        "book_appointment",
        "cancel_appointment",
        "reschedule_appointment",
        "dental_information",
    }

    return intent in interruptible_intents


async def _process_conversation_core(
    conversation: ConversationInput,
) -> ConversationResult:
    patient = await find_patient_by_phone(
        clinic_id=conversation.clinic_id,
        phone=conversation.sender_phone,
    )

    patient_was_created = patient is None

    if patient is None:
        patient = await upsert_patient_record(
            clinic_id=conversation.clinic_id,
            phone=conversation.sender_phone,
        )

    patient_id = patient["id"]

    patient_context = await build_patient_context(
        clinic_id=conversation.clinic_id,
        patient_id=patient_id,
    )

    preference_context = _format_patient_preferences(
        patient_context.preferences
        if patient_context is not None
        else {},
    )

    orchestration = await orchestrate_conversation_message(
        conversation,
        conversation_context=preference_context,
    )

    intent = orchestration.intent
    routed_message = orchestration.normalized_message

    if intent in {
        "book_appointment",
        "reschedule_appointment",
    }:
        routed_message = _apply_habitual_preferences(
            original_message=conversation.message,
            routed_message=routed_message,
            preferences=(
                patient_context.preferences
                if patient_context is not None
                else {}
            ),
            interpretation=orchestration.interpretation,
        )

    if patient_was_created:
        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            channel=conversation.channel,
            state="waiting_for_patient_name",
            context={
                "original_message": conversation.message,
                "detected_intent": intent,
            },
        )

        return ConversationResult(
            intent="patient_registration",
            patient_id=patient_id,
            reply=(
                "Bienvenue 😊 Avant de continuer, "
                "quel est votre nom et prénom ?"
            ),
        )
    conversation_state = None

    if patient_id is not None:
        conversation_state = await get_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            channel=conversation.channel,
        )

    active_context = (
        conversation_state["context"]
        if conversation_state is not None
        else {}
    ) or {}
    active_intent = active_context.get("intent")

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_patient_name"
    ):
        updated_patient = await update_patient_name(
            clinic_id=conversation.clinic_id,
            patient_id=patient["id"],
            full_name=conversation.message,
        )

        if updated_patient is None:
            return ConversationResult(
                intent="patient_registration",
                patient_id=patient["id"],
                reply=(
                    "Je n'ai pas bien compris votre nom. "
                    "Pouvez-vous m'indiquer votre nom et prénom ?"
                ),
            )

        original_message = active_context.get("original_message")

        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient["id"],
            channel=conversation.channel,
            state="idle",
            context={},
        )

        if not original_message:
            return ConversationResult(
                intent="patient_registration",
                patient_id=patient["id"],
                reply=(
                    f"Merci {updated_patient['full_name']} 😊 "
                    "Comment puis-je vous aider ?"
                ),
            )

        resumed_conversation = conversation.model_copy(
            update={
                "message": original_message,
                "patient_id": patient["id"],
            },
        )

        resumed_result = await _process_conversation_core(
            resumed_conversation,
        )

        return resumed_result.model_copy(
            update={
                "reply": (
                    f"Merci {updated_patient['full_name']} 😊\n\n"
                    f"{resumed_result.reply}"
                ),
            },
        )

    has_new_explicit_intent = _has_new_explicit_intent(intent)

    print(
        "[DEBUG][PROCESSOR]",
        {
            "message": conversation.message,
            "routed_message": routed_message,
            "intent": intent,
            "conversation_state": (
                conversation_state["state"]
                if conversation_state is not None
                else None
            ),
            "active_intent": active_intent,
            "has_new_explicit_intent": has_new_explicit_intent,
            "context": active_context,
        },
        flush=True,
    )

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_reschedule_date"
        and not has_new_explicit_intent
    ):
        return await handle_rescheduling_date_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
        )

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_reschedule_time"
        and not has_new_explicit_intent
    ):
        return await handle_rescheduling_time_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
        )

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_date"
        and not has_new_explicit_intent
    ):
        return await handle_booking_date_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
        )

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_time"
        and not has_new_explicit_intent
    ):
        return await handle_booking_time_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
        )


    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "waiting_for_confirmation"
        and not has_new_explicit_intent
    ):
        context = conversation_state["context"] or {}

        if is_correction_message(conversation.message):
            correction_parts = extract_message_parts(
                conversation.message,
            )
            active_workflow = context.get("intent")

            if active_workflow == "book_appointment":
                if correction_parts.date_text is not None:
                    return await handle_booking_date_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                    )

                if correction_parts.time_text is not None:
                    return await handle_booking_time_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                    )

                if (
                    correction_parts.practitioner_text is not None
                    or correction_parts.any_practitioner
                ):
                    return await handle_booking_time_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                    )

            if active_workflow == "reschedule_appointment":
                if correction_parts.date_text is not None:
                    return await handle_rescheduling_date_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                    )

                if correction_parts.time_text is not None:
                    return await handle_rescheduling_time_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                    )

        if context.get("intent") == "cancel_appointment":
            return await handle_cancellation_confirmation(
                clinic_id=conversation.clinic_id,
                channel=conversation.channel,
                patient=patient,
                message=conversation.message,
                current_context=context,
            )

        if context.get("intent") == "reschedule_appointment":
            return await handle_rescheduling_confirmation(
                clinic_id=conversation.clinic_id,
                channel=conversation.channel,
                patient=patient,
                message=conversation.message,
                current_context=context,
            )

        return await handle_booking_confirmation_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=context,
        )

    if (
        patient is not None
        and conversation_state is not None
        and conversation_state["state"] == "completed"
    ):
        answer = conversation.message.strip().lower()

        if answer in {
            "oui",
            "ok",
            "okay",
            "merci",
            "d'accord",
            "daccord",
        }:
            context = conversation_state["context"] or {}

            if (
                context.get("intent") == "cancel_appointment"
                and context.get("cancelled") is True
            ):
                return ConversationResult(
                    intent="cancel_appointment",
                    patient_id=patient_id,
                    reply="Ce rendez-vous est déjà annulé ✅",
                    metadata={
                        "appointment_id": context.get(
                            "appointment_id",
                        ),
                        "cancelled": True,
                    },
                )

            if context.get("confirmed") is True:
                return ConversationResult(
                    intent="book_appointment",
                    patient_id=patient_id,
                    reply=(
                        "Votre rendez-vous est déjà confirmé ✅ "
                        "Vous recevrez les informations du cabinet "
                        "selon les notifications configurées."
                    ),
                    metadata={
                        "appointment_id": context.get(
                            "appointment_id",
                        ),
                    },
                )

    if intent == "dental_information":
        conversation_context = format_history_for_llm(
            active_context,
        )

        knowledge_reply = await generate_knowledge_fallback(
            user_message=conversation.message,
            conversation_context=conversation_context,
        )

        if knowledge_reply is not None:
            return ConversationResult(
                intent="dental_information",
                patient_id=patient_id,
                reply=knowledge_reply,
                metadata={
                    "reply_source": "knowledge_fallback",
                },
            )

        return ConversationResult(
            intent="dental_information",
            patient_id=patient_id,
            reply=(
                "Cette question nécessite l'avis d'un professionnel "
                "du cabinet. Souhaitez-vous être mis en relation "
                "avec l'équipe ?"
            ),
            requires_human=True,
            metadata={
                "reply_source": "deterministic_fallback",
            },
        )

    if intent == "greeting":
        return handle_greeting(patient)

    if intent == "book_appointment":
        return await handle_booking(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=routed_message,
        )

    if intent == "cancel_appointment":
        return await handle_cancellation(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
        )

    if intent == "reschedule_appointment":
        return await handle_rescheduling(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=routed_message,
        )

    if intent == "clinic_information":
        return ConversationResult(
            intent=intent,
            patient_id=patient_id,
            reply=(
                "Je peux vous renseigner sur les horaires, "
                "l'adresse ou les informations de la clinique."
            ),
        )

    if intent == "treatment_pricing":
        return await handle_treatment_pricing(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
        )

    conversation_context = format_history_for_llm(
        active_context,
    )

    llm_result = await _process_with_llm_fallback(
        conversation=conversation,
        patient=patient,
        patient_id=patient_id,
        conversation_context=conversation_context,
    )

    if llm_result is not None:
        return llm_result

    knowledge_reply = await generate_knowledge_fallback(
        user_message=conversation.message,
        conversation_context=conversation_context,
    )

    if knowledge_reply is not None:
        return ConversationResult(
            intent="unknown",
            patient_id=patient_id,
            reply=knowledge_reply,
            metadata={
                "reply_source": "knowledge_fallback",
            },
        )

    return ConversationResult(
        intent="unknown",
        patient_id=patient_id,
        reply=(
            "Je n'ai pas encore compris votre demande. "
            "Pouvez-vous la reformuler ?"
        ),
        metadata={
            "reply_source": "deterministic_fallback",
        },
    )

# CHAT MODEL NATURAL REPLY WRAPPER
async def process_conversation(
    conversation: ConversationInput,
) -> ConversationResult:
    """
    Exécute le moteur métier, reformule la réponse naturellement,
    puis enregistre le tour dans la mémoire conversationnelle.

    La réponse métier reste utilisée automatiquement si le modèle
    conversationnel est indisponible.
    """

    result = await _process_conversation_core(conversation)

    natural_reply = await generate_natural_reply(
        ChatReplyContext(
            intent=result.intent,
            user_message=conversation.message,
            business_reply=result.reply,
            metadata=result.metadata,
        ),
    )

    final_result = (
        result
        if natural_reply == result.reply
        else result.model_copy(
            update={
                "reply": natural_reply,
            },
        )
    )

    if final_result.patient_id is not None:
        await append_conversation_turn(
            clinic_id=conversation.clinic_id,
            patient_id=final_result.patient_id,
            channel=conversation.channel,
            user_message=conversation.message,
            assistant_message=final_result.reply,
        )

    return final_result
