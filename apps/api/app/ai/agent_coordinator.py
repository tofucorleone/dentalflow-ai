from fastapi.encoders import jsonable_encoder

from app.ai.agent_response_composer import (
    AgentResponseCompositionError,
    compose_agent_reply,
)
from app.ai.agent_tools import execute_requested_tools
from app.ai.conversation_state import save_conversation_state
from app.ai.conversation_thread_state import (
    save_conversation_thread_state,
)
from app.ai.orchestrator import OrchestrationDecision
from app.ai.schemas import ConversationInput, ConversationResult
from app.ai.llm.client import LlmConfigurationError


async def handle_multi_tool_request(
    *,
    conversation: ConversationInput,
    orchestration: OrchestrationDecision,
    patient_id,
    thread_id=None,
) -> ConversationResult:
    """
    Exécute un plan multi-outils en lecture seule et compose
    une réponse naturelle unique.

    Cette fonction ne réserve, ne déplace et n'annule jamais
    de rendez-vous.
    """

    execution = await execute_requested_tools(
        clinic_id=conversation.clinic_id,
        requested_tools=orchestration.requested_tools,
    )

    try:
        reply = await compose_agent_reply(
            clinic_id=conversation.clinic_id,
            patient_message=conversation.message,
            primary_intent=orchestration.intent,
            execution=execution,
        )
    except (
        LlmConfigurationError,
        AgentResponseCompositionError,
    ):
        reply = (
            "J’ai bien compris votre demande, mais je ne peux pas "
            "composer une réponse complète pour le moment. "
            "Pouvez-vous reformuler ou préciser votre priorité ?"
        )

    slot_result = next(
        (
            result
            for result in execution.results
            if (
                result.name == "find_available_slots"
                and result.success
                and isinstance(result.data, dict)
            )
        ),
        None,
    )

    slots = jsonable_encoder(
        (
            slot_result.data.get("slots", [])
            if slot_result is not None
            else []
        )
    )

    if slots:
        state = "waiting_for_time"
        context = {
            "intent": "book_appointment",
            "requested_date_text": (
                slot_result.data.get("date_text")
            ),
            "requested_time_text": (
                slot_result.data.get("time_text")
            ),
            "suggested_slots": slots,
        }
    else:
        state = "idle"
        context = {
            "intent": orchestration.intent,
        }

    if patient_id is not None:
        await save_conversation_state(
            clinic_id=conversation.clinic_id,
            patient_id=patient_id,
            channel=conversation.channel,
            state=state,
            context=context,
            session_id=conversation.session_id,
        )
    elif thread_id is not None:
        await save_conversation_thread_state(
            clinic_id=conversation.clinic_id,
            thread_id=thread_id,
            state=state,
            context=context,
            session_id=conversation.session_id,
        )

    return ConversationResult(
        intent=orchestration.intent,
        patient_id=patient_id,
        reply=reply,
        metadata={
            "reply_source": "multi_tool_agent",
            "requested_tools": [
                tool.name
                for tool in orchestration.requested_tools
            ],
            "tool_results": execution.model_dump(
                mode="json",
            ),
        },
    )


__all__ = [
    "handle_multi_tool_request",
]
