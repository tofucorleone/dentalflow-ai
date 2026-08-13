from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse

from app.auth import current_user
from app.ai.conversation_thread import (
    get_or_create_conversation_thread,
    update_conversation_thread_after_message,
)
from app.ai.conversation_message import (
    create_conversation_message,
)
from app.conversations.realtime import (
    conversation_event_stream,
    publish_conversation_event,
)
from app.conversations.schemas import (
    ConversationExternalOutboundRequest,
    ConversationExternalOutboundResponse,
    ConversationMessageListResponse,
    ConversationSendRequest,
    ConversationSendResponse,
    ConversationThread,
    ConversationThreadListResponse,
)
from app.conversations.service import (
    build_conversation_list,
    build_conversation_messages,
    mark_conversation_read,
    mark_human_message_failed,
    mark_human_message_sent,
    prepare_human_message,
    require_conversation_thread,
)
from app.conversations.evolution_provider import (
    EvolutionSendError,
    send_evolution_text_message,
)
from app.db import connection
from app.deps import authenticated_clinic_id
from app.integrations.service import (
    resolve_active_integration,
)


router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.get(
    "",
    response_model=ConversationThreadListResponse,
)
async def conversations_list(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    thread_status: Literal[
        "open",
        "closed",
    ]
    | None = Query(
        default=None,
        alias="status",
    ),
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_conversation_list(
                cur=cur,
                clinic_id=current_clinic,
                limit=limit,
                offset=offset,
                thread_status=thread_status,
            )


@router.get(
    "/events",
    response_class=StreamingResponse,
)
async def conversation_events(
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> StreamingResponse:
    del user

    return StreamingResponse(
        conversation_event_stream(
            clinic_id=current_clinic,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/external-outbound",
    response_model=ConversationExternalOutboundResponse,
    status_code=201,
)
async def register_external_outbound_message(
    payload: ConversationExternalOutboundRequest,
    x_integration_secret: str | None = Header(
        default=None,
        alias="X-Integration-Secret",
    ),
) -> dict:
    integration = await resolve_active_integration(
        provider=payload.provider,
        provider_instance=payload.provider_instance,
        supplied_secret=x_integration_secret,
    )

    current_clinic = integration["clinic_id"]

    async with connection() as conn:
        async with conn.cursor() as cur:
            thread = await get_or_create_conversation_thread(
                cur=cur,
                clinic_id=current_clinic,
                patient_id=None,
                channel="whatsapp",
                sender_phone=payload.sender_phone,
                provider=payload.provider.strip().lower(),
                provider_instance=payload.provider_instance,
                external_thread_id=None,
            )

            message = await create_conversation_message(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread["id"],
                patient_id=thread.get("patient_id"),
                channel="whatsapp",
                direction="outbound",
                author_type="system",
                message_type="text",
                body=payload.message,
                external_id=payload.external_id,
                provider=payload.provider.strip().lower(),
                status="sent",
                requires_validation=False,
                metadata={
                    "source": "whatsapp_app",
                    "from_me": True,
                    "provider_instance": (
                        payload.provider_instance
                    ),
                },
            )

            created = bool(
                message.get("created", True)
            )

            if created:
                thread = (
                    await update_conversation_thread_after_message(
                        cur=cur,
                        thread_id=thread["id"],
                        direction="outbound",
                        patient_id=thread.get("patient_id"),
                    )
                )

        await conn.commit()

    if created:
        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.sent",
            data={
                "thread_id": str(thread["id"]),
                "message": message,
            },
        )

    return {
        "message": message,
        "created": created,
    }


@router.post(
    "/clear-history",
)
async def clear_conversation_history(
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM conversation_history
                WHERE clinic_id = %s
                """,
                (current_clinic,),
            )
            deleted_history = cur.rowcount

            await cur.execute(
                """
                DELETE FROM conversation_states
                WHERE clinic_id = %s
                """,
                (current_clinic,),
            )
            deleted_states = cur.rowcount

            await cur.execute(
                """
                DELETE FROM conversation_threads
                WHERE clinic_id = %s
                """,
                (current_clinic,),
            )
            deleted_threads = cur.rowcount

        await conn.commit()

    return {
        "cleared": True,
        "deleted": {
            "conversation_history": deleted_history,
            "conversation_states": deleted_states,
            "conversation_threads": deleted_threads,
        },
    }


@router.get(
    "/{thread_id}",
    response_model=ConversationThread,
)
async def conversation_detail(
    thread_id: UUID,
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await require_conversation_thread(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
            )


@router.post(
    "/{thread_id}/read",
)
async def conversation_mark_read(
    thread_id: UUID,
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            result = await mark_conversation_read(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
            )

            await conn.commit()

            return {
                "thread_id": result["id"],
                "unread_count": result["unread_count"],
                "updated_at": result["updated_at"],
            }


@router.get(
    "/{thread_id}/messages",
    response_model=ConversationMessageListResponse,
)
async def conversation_messages(
    thread_id: UUID,
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    del user

    async with connection() as conn:
        async with conn.cursor() as cur:
            return await build_conversation_messages(
                cur=cur,
                clinic_id=current_clinic,
                thread_id=thread_id,
                limit=limit,
                offset=offset,
            )


@router.post(
    "/{thread_id}/send",
    response_model=ConversationSendResponse,
    status_code=201,
)
async def send_conversation_message(
    thread_id: UUID,
    payload: ConversationSendRequest,
    current_clinic: UUID = Depends(
        authenticated_clinic_id
    ),
    user: dict = Depends(current_user),
) -> dict:
    user_id = user.get("id")

    if not isinstance(user_id, UUID):
        user_id = UUID(str(user_id))

    async with connection() as conn:
        async with conn.cursor() as cur:
            thread, prepared_message = (
                await prepare_human_message(
                    cur=cur,
                    clinic_id=current_clinic,
                    thread_id=thread_id,
                    user_id=user_id,
                    body=payload.message,
                )
            )

        await conn.commit()

    try:
        provider_result = (
            await send_evolution_text_message(
                instance=thread["provider_instance"],
                sender_phone=thread["sender_phone"],
                text=prepared_message["body"],
            )
        )
    except EvolutionSendError as exc:
        async with connection() as conn:
            async with conn.cursor() as cur:
                failed_message = (
                    await mark_human_message_failed(
                        cur=cur,
                        clinic_id=current_clinic,
                        message_id=prepared_message["id"],
                        error=str(exc),
                        status_code=exc.status_code,
                        response_body=exc.response_body,
                    )
                )

            await conn.commit()

        await publish_conversation_event(
            clinic_id=current_clinic,
            event_type="conversation.message.failed",
            data={
                "thread_id": str(thread_id),
                "message": failed_message,
            },
        )

        return {
            "message": failed_message,
        }

    async with connection() as conn:
        async with conn.cursor() as cur:
            sent_message = await mark_human_message_sent(
                cur=cur,
                clinic_id=current_clinic,
                message_id=prepared_message["id"],
                external_id=provider_result[
                    "external_id"
                ],
                provider_response=provider_result[
                    "response"
                ],
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

    return {
        "message": sent_message,
    }
