from uuid import UUID

from fastapi import HTTPException, status

from app.conversations.repository import (
    count_conversation_messages,
    count_conversation_threads,
    get_conversation_thread,
    list_conversation_messages,
    list_conversation_threads,
    mark_conversation_thread_read,
)


async def build_conversation_list(
    *,
    cur,
    clinic_id: UUID,
    limit: int,
    offset: int,
    thread_status: str | None,
) -> dict:
    items = await list_conversation_threads(
        cur=cur,
        clinic_id=clinic_id,
        limit=limit,
        offset=offset,
        status=thread_status,
    )

    total = await count_conversation_threads(
        cur=cur,
        clinic_id=clinic_id,
        status=thread_status,
    )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


async def require_conversation_thread(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
) -> dict:
    thread = await get_conversation_thread(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation introuvable.",
        )

    return thread


async def mark_conversation_read(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
) -> dict:
    await require_conversation_thread(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    thread = await mark_conversation_thread_read(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation introuvable.",
        )

    return thread


async def build_conversation_messages(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
    limit: int,
    offset: int,
) -> dict:
    await require_conversation_thread(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    items = await list_conversation_messages(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
        limit=limit,
        offset=offset,
    )

    total = await count_conversation_messages(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    return {
        "thread_id": thread_id,
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


__all__ = [
    "build_conversation_list",
    "build_conversation_messages",
    "require_conversation_thread",
    "prepare_human_message",
    "mark_human_message_sent",
    "mark_human_message_failed",
]


async def prepare_human_message(
    *,
    cur,
    clinic_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    body: str,
) -> tuple[dict, dict]:
    from fastapi import HTTPException, status

    from app.ai.conversation_message import (
        create_conversation_message,
    )
    from app.ai.conversation_thread import (
        update_conversation_thread_after_message,
    )

    thread = await require_conversation_thread(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
    )

    if thread["status"] != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette conversation est fermée.",
        )

    if thread["channel"] != "whatsapp":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "L'envoi depuis l'Inbox est actuellement "
                "disponible uniquement pour WhatsApp."
            ),
        )

    if thread.get("provider") not in {
        None,
        "evolution",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Le fournisseur de cette conversation "
                "n'est pas supporté."
            ),
        )

    provider_instance = (
        thread.get("provider_instance") or ""
    ).strip()

    if not provider_instance:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Aucune instance Evolution n'est associée "
                "à cette conversation."
            ),
        )

    message = await create_conversation_message(
        cur=cur,
        clinic_id=clinic_id,
        thread_id=thread_id,
        patient_id=thread.get("patient_id"),
        sent_by_user_id=user_id,
        channel="whatsapp",
        direction="outbound",
        author_type="human",
        message_type="text",
        body=body,
        provider="evolution",
        status="prepared",
        requires_validation=False,
        metadata={
            "source": "conversation_inbox",
            "provider_instance": provider_instance,
        },
    )

    await update_conversation_thread_after_message(
        cur=cur,
        thread_id=thread_id,
        direction="outbound",
        patient_id=thread.get("patient_id"),
    )

    return thread, message


async def mark_human_message_sent(
    *,
    cur,
    clinic_id: UUID,
    message_id: UUID,
    external_id: str | None,
    provider_response: dict,
) -> dict:
    from app.ai.conversation_message import (
        update_conversation_message_status,
    )

    return await update_conversation_message_status(
        cur=cur,
        clinic_id=clinic_id,
        message_id=message_id,
        status="sent",
        external_id=external_id,
        metadata_patch={
            "provider_delivery": {
                "accepted": True,
                "response": provider_response,
            }
        },
    )


async def mark_human_message_failed(
    *,
    cur,
    clinic_id: UUID,
    message_id: UUID,
    error: str,
    status_code: int | None = None,
    response_body: str | None = None,
) -> dict:
    from app.ai.conversation_message import (
        update_conversation_message_status,
    )

    provider_delivery = {
        "accepted": False,
        "error": error,
    }

    if status_code is not None:
        provider_delivery["status_code"] = status_code

    if response_body:
        provider_delivery["response_body"] = response_body

    return await update_conversation_message_status(
        cur=cur,
        clinic_id=clinic_id,
        message_id=message_id,
        status="failed",
        metadata_patch={
            "provider_delivery": provider_delivery,
        },
    )
