from app.ai.context import build_patient_context
from app.ai.context_engine import (
    save_patient_conversation_summary,
    save_patient_preferences,
)
from app.ai.conversation_corrections import is_correction_message
from app.ai.confirmation_parser import parse_confirmation
from app.ai.conversation_state import (
    append_conversation_turn,
    get_conversation_state,
    reset_conversation_session,
    save_conversation_state,
    set_conversation_session,
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
from app.ai.handlers.social import (
    handle_goodbye,
    handle_thanks,
)
from app.ai.handlers.treatment_pricing import handle_treatment_pricing
from app.ai.message_parser import extract_message_parts
from app.ai.llm.client import LlmConfigurationError
from app.ai.llm.chat_model import (
    ChatReplyContext,
    generate_natural_reply,
)
from app.ai.llm.history_formatter import format_history_for_llm
from app.ai.llm.knowledge_fallback import generate_knowledge_fallback
from app.ai.llm.preference_extractor import (
    PreferenceExtractionError,
    extract_patient_preferences,
)
from app.ai.llm.conversation_summarizer import (
    ConversationSummaryError,
    summarize_conversation_history,
)
from app.ai.llm.conversation_interpreter import (
    ConversationInterpretationError,
    interpret_conversation_message,
)
from app.ai.agent_coordinator import (
    handle_multi_tool_request,
)
from app.ai.orchestrator import orchestrate_conversation_message
from app.ai.patient_matcher import find_patient_by_phone
from app.ai.patient_name import extract_patient_name
from app.ai.conversation_thread_state import (
    delete_conversation_thread_state,
    get_conversation_thread_state,
    save_conversation_thread_state,
)
from app.patient_service import (
    update_patient_name,
    upsert_patient_record,
)
from app.ai.schemas import (
    ConversationInput,
    ConversationResult,
)


def _conversation_thread_id(
    conversation: ConversationInput,
):
    raw_thread_id = conversation.metadata.get("thread_id")

    if raw_thread_id is None:
        return None

    try:
        from uuid import UUID
        return UUID(str(raw_thread_id))
    except (TypeError, ValueError):
        return None


async def _get_active_conversation_state(
    *,
    clinic_id,
    channel,
    patient_id=None,
    thread_id=None,
    session_id=None,
):
    if patient_id is not None:
        return await get_conversation_state(
            clinic_id=clinic_id,
            patient_id=patient_id,
            channel=channel,
            session_id=session_id,
        )

    if thread_id is not None:
        return await get_conversation_thread_state(
            clinic_id=clinic_id,
            thread_id=thread_id,
            session_id=session_id,
        )

    return None


async def _save_active_conversation_state(
    *,
    clinic_id,
    channel,
    state,
    context,
    patient_id=None,
    thread_id=None,
    session_id=None,
):
    if patient_id is not None:
        return await save_conversation_state(
            clinic_id=clinic_id,
            patient_id=patient_id,
            channel=channel,
            state=state,
            context=context,
            session_id=session_id,
        )

    if thread_id is not None:
        return await save_conversation_thread_state(
            clinic_id=clinic_id,
            thread_id=thread_id,
            state=state,
            context=context,
            session_id=session_id,
        )

    raise RuntimeError(
        "Impossible de sauvegarder l'état conversationnel : "
        "patient_id et thread_id sont absents."
    )


async def _summarize_history_if_needed(
    *,
    conversation: ConversationInput,
    patient_id,
    updated_state: dict | None,
    minimum_messages: int = 16,
    retained_messages: int = 8,
) -> None:
    """
    Résume une conversation longue puis conserve seulement les derniers
    messages utiles dans l'état conversationnel.

    Une erreur du LLM ou de stockage ne bloque jamais la réponse patient.
    """
    if updated_state is None:
        return

    context = updated_state.get("context")

    if not isinstance(context, dict):
        return

    history = context.get("history")

    if not isinstance(history, list):
        return

    if len(history) < minimum_messages:
        return

    cleaned_history = [
        message
        for message in history
        if (
            isinstance(message, dict)
            and isinstance(message.get("role"), str)
            and isinstance(message.get("content"), str)
        )
    ]

    if len(cleaned_history) < minimum_messages:
        return

    patient_context = await build_patient_context(
        clinic_id=conversation.clinic_id,
        patient_id=patient_id,
    )

    previous_summary = (
        patient_context.summary
        if patient_context is not None
        else None
    )

    try:
        summary_result = await summarize_conversation_history(
            history=cleaned_history,
            previous_summary=previous_summary,
        )

        await save_patient_conversation_summary(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            summary=summary_result.summary,
            last_goal=summary_result.last_goal,
        )

        trimmed_context = dict(context)
        trimmed_context["history"] = cleaned_history[
            -retained_messages:
        ]

        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            channel=conversation.channel,
            state=updated_state["state"],
            context=trimmed_context,
        )
    except (
        LlmConfigurationError,
        ConversationSummaryError,
    ) as exc:
        print(
            "[WARNING][CONVERSATION_SUMMARY]",
            {
                "patient_id": str(patient_id),
                "error": str(exc),
            },
            flush=True,
        )


async def _remember_explicit_preferences(
    *,
    conversation: ConversationInput,
    patient_id,
) -> dict:
    """
    Mémorise uniquement les préférences durables et explicites.

    Une erreur d'extraction ou de stockage ne doit jamais bloquer
    le moteur conversationnel principal.
    """
    try:
        extraction = await extract_patient_preferences(
            clinic_id=conversation.clinic_id,
            message=conversation.message,
        )
    except (
        LlmConfigurationError,
        PreferenceExtractionError,
    ):
        return {}

    if (
        not extraction.has_preferences
        or extraction.confidence < 0.85
    ):
        return {}

    preferences = {
        key: value
        for key, value in {
            "preferred_practitioner": (
                extraction.preferred_practitioner
            ),
            "preferred_day": extraction.preferred_day,
            "preferred_time": extraction.preferred_time,
            "preferred_language": extraction.preferred_language,
        }.items()
        if value is not None
    }

    if not preferences:
        return {}

    try:
        return await save_patient_preferences(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            preferences=preferences,
        )
    except Exception as exc:
        print(
            "[WARNING][PREFERENCE_MEMORY]",
            {
                "patient_id": str(patient_id),
                "error": str(exc),
            },
            flush=True,
        )
        return {}


def _message_needs_clinical_context(
    message: str,
) -> bool:
    normalized = message.strip().lower()

    clinical_markers = (
        "mon dossier",
        "mes documents",
        "mon document",
        "ma radio",
        "ma radiographie",
        "mon ordonnance",
        "mon compte rendu",
        "mon compte-rendu",
        "mes antécédents",
        "mes antecedents",
        "mon historique médical",
        "mon historique medical",
        "dans mon dossier",
        "selon ma radio",
        "d'après ma radio",
        "d’apres ma radio",
        "allergie",
        "allergique",
        "traitement en cours",
        "médicament",
        "medicament",
    )

    return any(
        marker in normalized
        for marker in clinical_markers
    )


def _format_clinical_context(
    *,
    medical_history: list[str],
    recent_documents: list[str],
    notes: list[str],
) -> str | None:
    sections: list[str] = []

    if medical_history:
        sections.append(
            "Historique médical actif :\n"
            + "\n".join(
                f"- {item}"
                for item in medical_history
            )
        )

    if recent_documents:
        sections.append(
            "Documents récents :\n"
            + "\n".join(
                f"- {item}"
                for item in recent_documents
            )
        )

    if notes:
        sections.append(
            "Notes internes pertinentes :\n"
            + "\n".join(
                f"- {item}"
                for item in notes
            )
        )

    if not sections:
        return None

    return (
        "\n\n".join(sections)
        + "\n\n"
        + (
            "Ce contexte est informatif uniquement. "
            "Ne pose aucun diagnostic, ne prescris aucun traitement "
            "et ne déduis jamais une action non confirmée."
        )
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
    patient: dict | None,
    patient_id,
    thread_id=None,
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
            thread_id=thread_id,
            session_id=conversation.session_id,
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


def _has_new_explicit_intent(
    intent: str,
    conversation_state: str | None = None,
) -> bool:
    interruptible_intents = {
        "cancel_appointment",
        "reschedule_appointment",
        "dental_information",
        "human_handoff",
        "thanks",
        "goodbye",
    }

    if (
        intent == "book_appointment"
        and conversation_state in {
            "waiting_for_date",
            "waiting_for_time",
            "waiting_for_confirmation",
        }
    ):
        return False

    return intent in interruptible_intents or (
        intent == "book_appointment"
        and conversation_state is None
    )


async def _process_conversation_core(
    conversation: ConversationInput,
) -> ConversationResult:
    patient = await find_patient_by_phone(
        clinic_id=conversation.clinic_id,
        phone=conversation.sender_phone,
    )

    thread_state = None
    thread_id = _conversation_thread_id(conversation)

    if patient is None and thread_id is not None:
        thread_state = await get_conversation_thread_state(
            clinic_id=conversation.clinic_id,
            thread_id=thread_id,
            session_id=conversation.session_id,
        )

    patient_id = (
        patient["id"]
        if patient is not None
        else None
    )

    if patient_id is not None:
        await _remember_explicit_preferences(
            conversation=conversation,
            patient_id=patient_id,
        )

        patient_context = await build_patient_context(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
        )
    else:
        patient_context = None

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

    conversation_state = await _get_active_conversation_state(
        clinic_id=conversation.clinic_id,
        channel=conversation.channel,
        patient_id=patient_id,
        thread_id=thread_id,
        session_id=conversation.session_id,
    )

    if (
        conversation_state is None
        and conversation.session_id is not None
    ):
        conversation_state = await _save_active_conversation_state(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient_id=patient_id,
            thread_id=thread_id,
            session_id=conversation.session_id,
            state="idle",
            context={},
        )

    active_context = (
        conversation_state["context"]
        if conversation_state is not None
        else {}
    ) or {}
    active_intent = active_context.get("intent")

    if (
        conversation_state is not None
        and conversation_state["state"] == "waiting_for_patient_name"
    ):
        patient_name = extract_patient_name(
            conversation.message,
        )

        if patient_name is None:
            if (
                patient is None
                and thread_id is not None
                and active_context.get("intent") == "book_appointment"
            ):
                correction_parts = extract_message_parts(
                    conversation.message,
                )

                booking_result = None

                if correction_parts.date_text is not None:
                    booking_result = await handle_booking_date_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=None,
                        message=conversation.message,
                        current_context=active_context,
                        thread_id=thread_id,
                        session_id=conversation.session_id,
                    )

                elif (
                    correction_parts.time_text is not None
                    or correction_parts.practitioner_text is not None
                    or correction_parts.any_practitioner
                ):
                    booking_result = await handle_booking_time_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=None,
                        message=conversation.message,
                        current_context=active_context,
                        thread_id=thread_id,
                        session_id=conversation.session_id,
                    )

                if booking_result is not None:
                    updated_thread_state = (
                        await get_conversation_thread_state(
                            clinic_id=conversation.clinic_id,
                            thread_id=thread_id,
                            session_id=conversation.session_id,
                        )
                    )

                    updated_context = (
                        updated_thread_state["context"]
                        if updated_thread_state is not None
                        else active_context
                    ) or {}

                    await save_conversation_thread_state(
                        clinic_id=conversation.clinic_id,
                        thread_id=thread_id,
                        session_id=conversation.session_id,
                        state="waiting_for_patient_name",
                        context={
                            **updated_context,
                            "name_required": True,
                        },
                    )

                    return booking_result.model_copy(
                        update={
                            "patient_id": None,
                            "reply": (
                                f"{booking_result.reply}\n\n"
                                "Pour finaliser votre dossier, "
                                "pouvez-vous aussi m'indiquer "
                                "votre nom et prénom ?"
                            ),
                        },
                    )

            incidental_result = None

            if intent == "treatment_pricing":
                incidental_result = await handle_treatment_pricing(
                    clinic_id=conversation.clinic_id,
                    patient_id=None,
                )

            elif intent == "clinic_information":
                incidental_result = ConversationResult(
                    intent="clinic_information",
                    patient_id=None,
                    reply=(
                        "Je peux vous renseigner sur les horaires, "
                        "l'adresse ou les informations de la clinique."
                    ),
                )

            elif intent == "dental_information":
                conversation_context = format_history_for_llm(
                    active_context,
                )

                knowledge_reply = await generate_knowledge_fallback(
                    user_message=conversation.message,
                    conversation_context=conversation_context,
                    clinical_context=None,
                )

                if knowledge_reply is not None:
                    incidental_result = ConversationResult(
                        intent="dental_information",
                        patient_id=None,
                        reply=knowledge_reply,
                        metadata={
                            "reply_source": "knowledge_fallback",
                        },
                    )
                else:
                    incidental_result = ConversationResult(
                        intent="dental_information",
                        patient_id=None,
                        requires_human=True,
                        reply=(
                            "Cette question nécessite l'avis "
                            "d'un professionnel du cabinet."
                        ),
                    )

            if incidental_result is not None:
                return incidental_result.model_copy(
                    update={
                        "patient_id": None,
                        "reply": (
                            f"{incidental_result.reply}\n\n"
                            "Et pour finaliser votre rendez-vous, "
                            "pouvez-vous m'indiquer votre nom et prénom ?"
                        ),
                    },
                )

            return ConversationResult(
                intent="patient_registration",
                patient_id=patient_id,
                reply=(
                    "Je n'ai pas identifié un nom et prénom valides "
                    "dans votre message. "
                    "Pour finaliser le rendez-vous, pouvez-vous "
                    "m'indiquer uniquement votre nom et prénom ?"
                ),
            )

        # Ancien comportement conservé pour les éventuels dossiers
        # déjà créés avant cette évolution.
        if patient is not None:
            updated_patient = await update_patient_name(
                clinic_id=conversation.clinic_id,
                patient_id=patient["id"],
                full_name=patient_name,
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

            return ConversationResult(
                intent="patient_registration",
                patient_id=patient["id"],
                reply=(
                    f"Merci {updated_patient['full_name']} 😊 "
                    "Votre dossier est maintenant complété."
                ),
            )

        if thread_id is None:
            return ConversationResult(
                intent="patient_registration",
                patient_id=None,
                requires_human=True,
                reply=(
                    "Je n'ai pas pu rattacher votre dossier "
                    "à cette conversation. "
                    "L'équipe du cabinet va pouvoir vous aider."
                ),
            )

        # Le patient n'est créé qu'ici :
        # après confirmation du créneau ET validation stricte du nom.
        created_patient = await upsert_patient_record(
            clinic_id=conversation.clinic_id,
            phone=conversation.sender_phone,
            full_name=patient_name,
        )

        created_patient_id = created_patient["id"]

        # Le créneau confirmé passe maintenant du stockage temporaire
        # du thread vers l'état conversationnel du vrai patient.
        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=created_patient_id,
            channel=conversation.channel,
            state="waiting_for_confirmation",
            context=active_context,
            session_id=conversation.session_id,
        )

        await delete_conversation_thread_state(
            clinic_id=conversation.clinic_id,
            thread_id=thread_id,
            session_id=conversation.session_id,
        )

        # Le patient avait déjà confirmé le créneau avant que son nom
        # soit demandé. On reprend donc directement cette confirmation.
        booking_result = await handle_booking_confirmation_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=created_patient,
            message="oui",
            current_context=active_context,
        )

        return booking_result.model_copy(
            update={
                "reply": (
                    f"Merci {created_patient['full_name']} 😊\n\n"
                    f"{booking_result.reply}"
                ),
            },
        )

    workflow_action = getattr(
        orchestration.interpretation,
        "workflow_action",
        "none",
    ) if orchestration.interpretation is not None else "none"

    if (
        conversation_state is not None
        and conversation_state["state"] == "waiting_for_date"
        and active_intent == "book_appointment"
        and workflow_action == "abandon"
    ):
        await _save_active_conversation_state(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient_id=patient_id,
            thread_id=thread_id,
            session_id=conversation.session_id,
            state="idle",
            context={},
        )

        return ConversationResult(
            intent="book_appointment",
            patient_id=patient_id,
            reply=(
                "D'accord, j'abandonne cette nouvelle demande "
                "de rendez-vous. Votre rendez-vous existant "
                "reste inchangé."
            ),
        )

    has_new_explicit_intent = _has_new_explicit_intent(
        intent,
        conversation_state["state"]
        if conversation_state is not None
        else None,
    )

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

    requested_tools = getattr(
        orchestration,
        "requested_tools",
        [],
    )

    is_active_booking_continuation = (
        conversation_state is not None
        and active_intent == "book_appointment"
        and intent in {
            "book_appointment",
            "unknown",
        }
        and conversation_state["state"] in {
            "waiting_for_date",
            "waiting_for_time",
            "waiting_for_confirmation",
        }
    )

    if len(requested_tools) >= 2:
        return await handle_multi_tool_request(
            conversation=conversation,
            orchestration=orchestration,
            patient_id=patient_id,
            thread_id=thread_id,
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
        conversation_state is not None
        and conversation_state["state"] == "waiting_for_date"
        and not has_new_explicit_intent
    ):
        return await handle_booking_date_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
            thread_id=thread_id,
            session_id=conversation.session_id,
        )

    if (
        conversation_state is not None
        and conversation_state["state"] == "waiting_for_time"
        and (
            not has_new_explicit_intent
            or (
                active_intent == "book_appointment"
                and intent == "book_appointment"
            )
        )
    ):
        return await handle_booking_time_response(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=conversation.message,
            current_context=conversation_state["context"],
            thread_id=thread_id,
            session_id=conversation.session_id,
        )


    if (
        conversation_state is not None
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
                        thread_id=thread_id,
                        session_id=conversation.session_id,
                    )

                if correction_parts.time_text is not None:
                    return await handle_booking_time_response(
                        clinic_id=conversation.clinic_id,
                        channel=conversation.channel,
                        patient=patient,
                        message=conversation.message,
                        current_context=context,
                        thread_id=thread_id,
                        session_id=conversation.session_id,
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
                        thread_id=thread_id,
                        session_id=conversation.session_id,
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

        if (
            context.get("intent") == "book_appointment"
            and patient is None
        ):
            confirmation = parse_confirmation(
                conversation.message,
            )

            if confirmation is False:
                await _save_active_conversation_state(
                    clinic_id=conversation.clinic_id,
                    channel=conversation.channel,
                    patient_id=None,
                    thread_id=thread_id,
                    session_id=conversation.session_id,
                    state="completed",
                    context={
                        **context,
                        "confirmed": False,
                    },
                )

                return ConversationResult(
                    intent="book_appointment",
                    patient_id=None,
                    reply=(
                        "Très bien, le rendez-vous n'a pas été créé. "
                        "Je reste disponible si vous souhaitez "
                        "un autre créneau."
                    ),
                )

            if confirmation is None:
                return ConversationResult(
                    intent="book_appointment",
                    patient_id=None,
                    reply=(
                        "Pouvez-vous répondre par « oui » pour confirmer "
                        "ou « non » pour annuler ?"
                    ),
                )

            await _save_active_conversation_state(
                clinic_id=conversation.clinic_id,
                channel=conversation.channel,
                patient_id=None,
                thread_id=thread_id,
                session_id=conversation.session_id,
                state="waiting_for_patient_name",
                context={
                    **context,
                    "confirmed": True,
                },
            )

            return ConversationResult(
                intent="patient_registration",
                patient_id=None,
                reply=(
                    "Parfait 😊 Pour finaliser ce rendez-vous, "
                    "pouvez-vous m'indiquer votre nom et prénom ?"
                ),
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

    if intent == "preference_update":
        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            channel=conversation.channel,
            state="idle",
            context={},
        )

        return ConversationResult(
            intent="preference_update",
            patient_id=patient_id,
            reply=(
                "C’est bien noté 😊 "
                "Je tiendrai compte de cette préférence "
                "pour vos prochaines demandes."
            ),
            metadata={
                "preferences": (
                    patient_context.preferences
                    if patient_context is not None
                    else {}
                ),
                "reply_source": "preference_memory",
            },
        )

    if intent == "human_handoff":
        return ConversationResult(
            intent="human_handoff",
            patient_id=patient_id,
            requires_human=True,
            reply=(
                "Votre demande nécessite l'avis de l'équipe du cabinet. "
                "Je vais vous mettre en relation avec un professionnel."
            ),
            metadata={
                "reply_source": "human_handoff",
            },
        )

    if intent == "dental_information":
        conversation_context = format_history_for_llm(
            active_context,
        )

        clinical_context = None

        if (
            patient_context is not None
            and _message_needs_clinical_context(
                conversation.message,
            )
        ):
            clinical_context = _format_clinical_context(
                medical_history=patient_context.medical_history,
                recent_documents=patient_context.recent_documents,
                notes=patient_context.notes,
            )

        knowledge_reply = await generate_knowledge_fallback(
            user_message=conversation.message,
            conversation_context=conversation_context,
            clinical_context=clinical_context,
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

    if intent == "thanks":
        return handle_thanks(patient)

    if intent == "goodbye":
        return handle_goodbye(patient)

    if intent == "greeting":
        return handle_greeting(patient)

    if intent == "book_appointment":
        return await handle_booking(
            clinic_id=conversation.clinic_id,
            channel=conversation.channel,
            patient=patient,
            message=routed_message,
            thread_id=thread_id,
            session_id=conversation.session_id,
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
        thread_id=thread_id,
        conversation_context=conversation_context,
    )

    if llm_result is not None:
        return llm_result

    clinical_context = None

    if (
        patient_context is not None
        and _message_needs_clinical_context(
            conversation.message,
        )
    ):
        clinical_context = _format_clinical_context(
            medical_history=patient_context.medical_history,
            recent_documents=patient_context.recent_documents,
            notes=patient_context.notes,
        )

    knowledge_reply = await generate_knowledge_fallback(
        user_message=conversation.message,
        conversation_context=conversation_context,
        clinical_context=clinical_context,
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
async def _process_conversation_with_active_session(
    conversation: ConversationInput,
) -> ConversationResult:
    """
    Exécute le moteur métier, reformule la réponse naturellement,
    puis enregistre le tour dans la mémoire conversationnelle.

    La réponse métier reste utilisée automatiquement si le modèle
    conversationnel est indisponible.
    """

    result = await _process_conversation_core(conversation)

    patient_context = None

    if result.patient_id is not None:
        patient_context = await build_patient_context(
            clinic_id=conversation.clinic_id,
            patient_id=result.patient_id,
        )

    natural_reply = await generate_natural_reply(
        ChatReplyContext(
            intent=result.intent,
            user_message=conversation.message,
            business_reply=result.reply,
            patient_name=(
                patient_context.patient_name
                if patient_context is not None
                else None
            ),
            patient_summary=(
                patient_context.summary
                if patient_context is not None
                else None
            ),
            patient_preferences=(
                patient_context.preferences
                if patient_context is not None
                else {}
            ),
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
        updated_state = await append_conversation_turn(
            clinic_id=conversation.clinic_id,
            patient_id=final_result.patient_id,
            channel=conversation.channel,
            user_message=conversation.message,
            assistant_message=final_result.reply,
        )

        await _summarize_history_if_needed(
            conversation=conversation,
            patient_id=final_result.patient_id,
            updated_state=updated_state,
        )

    return final_result


async def process_conversation(
    conversation: ConversationInput,
) -> ConversationResult:
    """
    Active la session conversationnelle pendant tout le traitement.

    Les canaux sans session explicite continuent à utiliser
    la conversation par défaut avec session_id=None.
    """

    session_token = set_conversation_session(
        conversation.session_id,
    )

    try:
        return await _process_conversation_with_active_session(
            conversation,
        )
    finally:
        reset_conversation_session(session_token)

