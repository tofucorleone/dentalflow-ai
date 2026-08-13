from uuid import UUID

from fastapi import APIRouter, Depends

from app.ai.controlled_conversation import (
    process_controlled_conversation,
)
from app.ai.processor import process_conversation
from app.ai.schemas import (
    ControlledConversationResponse,
    ConversationInput,
    ConversationRequest,
    ConversationResult,
)
from app.conversations.evolution_provider import (
    EvolutionConfigurationError,
    EvolutionSendError,
    send_evolution_text_message,
)
from app.conversations.realtime import (
    publish_conversation_event,
)
from app.conversations.service import (
    mark_human_message_failed,
    mark_human_message_sent,
)
from app.db import connection
from app.deps import clinic_id


router = APIRouter(
    prefix="/ai",
    tags=["IA conversationnelle"],
)


async def mark_ai_message_failed(
    *,
    current_clinic: UUID,
    message_id: UUID,
    error: str,
    status_code: int | None = None,
    response_body: str | None = None,
) -> dict:
    async with connection() as conn:
        async with conn.cursor() as cur:
            failed_message = await mark_human_message_failed(
                cur=cur,
                clinic_id=current_clinic,
                message_id=message_id,
                error=error,
                status_code=status_code,
                response_body=response_body,
            )

        await conn.commit()

    return failed_message


@router.post(
    "/conversation",
    response_model=ControlledConversationResponse,
)
async def controlled_conversation(
    payload: ConversationRequest,
    current_clinic=Depends(clinic_id),
) -> ControlledConversationResponse:
    conversation = ConversationInput(
        clinic_id=current_clinic,
        **payload.model_dump(),
    )

    async with connection() as conn:
        async with conn.cursor() as cur:
            result = await process_controlled_conversation(
                cur=cur,
                conversation=conversation,
            )

        await conn.commit()

    result_metadata = result.metadata or {}

    if result_metadata.get("duplicate_message"):
        return result

    thread_id = result_metadata.get("thread_id")
    inbound_message_id = result_metadata.get(
        "inbound_message_id"
    )
    outbound_message_id = result_metadata.get(
        "outbound_message_id"
    )

    if thread_id and inbound_message_id:
        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.received",
            data={
                "thread_id": str(thread_id),
                "message_id": str(inbound_message_id),
            },
        )

    if not (
        thread_id
        and outbound_message_id
        and result.reply
    ):
        return result

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type="conversation.message.prepared",
        data={
            "thread_id": str(thread_id),
            "message_id": str(outbound_message_id),
        },
    )

    metadata = conversation.metadata or {}
    provider = str(
        metadata.get("provider") or ""
    ).strip()
    provider_instance = str(
        metadata.get("provider_instance") or ""
    ).strip()

    message_id = UUID(str(outbound_message_id))

    if provider != "evolution":
        failed_message = await mark_ai_message_failed(
            current_clinic=current_clinic,
            message_id=message_id,
            error=(
                "Le fournisseur Evolution est requis "
                "pour envoyer la réponse IA."
            ),
        )

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        return result

    if not provider_instance:
        failed_message = await mark_ai_message_failed(
            current_clinic=current_clinic,
            message_id=message_id,
            error=(
                "Aucune instance Evolution n'est associée "
                "à la conversation."
            ),
        )

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        return result

    try:
        provider_result = await send_evolution_text_message(
            instance=provider_instance,
            sender_phone=conversation.sender_phone,
            text=result.reply,
        )
    except EvolutionSendError as exc:
        failed_message = await mark_ai_message_failed(
            current_clinic=current_clinic,
            message_id=message_id,
            error=str(exc),
            status_code=exc.status_code,
            response_body=exc.response_body,
        )

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        return result
    except (
        EvolutionConfigurationError,
        ValueError,
    ) as exc:
        failed_message = await mark_ai_message_failed(
            current_clinic=current_clinic,
            message_id=message_id,
            error=str(exc),
        )

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        return result

    async with connection() as conn:
        async with conn.cursor() as cur:
            sent_message = await mark_human_message_sent(
                cur=cur,
                clinic_id=current_clinic,
                message_id=message_id,
                external_id=provider_result["external_id"],
                provider_response=provider_result["response"],
            )

        await conn.commit()

    await publish_conversation_event(
        clinic_id=current_clinic,
        event_type="conversation.message.sent",
        data={
            "thread_id": str(thread_id),
            "message": sent_message,
        },
    )

    return result


@router.post(
    "/conversation/test",
    response_model=ConversationResult,
)
async def test_conversation(
    payload: ConversationRequest,
    current_clinic=Depends(clinic_id),
) -> ConversationResult:
    conversation = ConversationInput(
        clinic_id=current_clinic,
        **payload.model_dump(),
    )

    return await process_conversation(conversation)
