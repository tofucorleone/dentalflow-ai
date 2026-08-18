from app.ai.conversation_control import (
    automatic_reply_allowed,
    get_conversation_control,
)
from app.ai.conversation_message import (
    create_conversation_message,
)
from app.ai.conversation_thread import (
    get_or_create_conversation_thread,
    update_conversation_thread_after_message,
)
from app.ai.processor import process_conversation
from app.appointment_confirmation_service import (
    handle_appointment_confirmation_reply,
)
from app.ai.message_debounce import (
    debounce_conversation_message,
)
from app.ai.schemas import (
    ControlledConversationResponse,
    ConversationInput,
)


def optional_metadata_string(
    metadata: dict,
    key: str,
) -> str | None:
    value = metadata.get(key)

    if value is None:
        return None

    normalized = str(value).strip()

    return normalized or None


async def process_controlled_conversation(
    *,
    cur,
    conversation: ConversationInput,
) -> ControlledConversationResponse:
    """
    Enregistre le message entrant, applique le contrôle humain,
    puis enregistre la réponse préparée par l'IA.

    Un webhook entrant déjà enregistré ne déclenche jamais
    une deuxième réponse automatique.
    """

    provider = optional_metadata_string(
        conversation.metadata,
        "provider",
    )
    provider_instance = optional_metadata_string(
        conversation.metadata,
        "provider_instance",
    )
    external_thread_id = optional_metadata_string(
        conversation.metadata,
        "external_thread_id",
    )

    thread = await get_or_create_conversation_thread(
        cur=cur,
        clinic_id=conversation.clinic_id,
        patient_id=conversation.patient_id,
        channel=conversation.channel,
        sender_phone=conversation.sender_phone,
        provider=provider,
        provider_instance=provider_instance,
        external_thread_id=external_thread_id,
    )

    # Le processor peut persister un état temporaire de thread
    # depuis une autre connexion PostgreSQL. Le thread doit donc
    # être visible avant l'appel au moteur conversationnel.
    await cur.connection.commit()

    inbound_message = await create_conversation_message(
        cur=cur,
        clinic_id=conversation.clinic_id,
        thread_id=thread["id"],
        patient_id=conversation.patient_id,
        channel=conversation.channel,
        direction="inbound",
        author_type="patient",
        message_type="text",
        body=conversation.message,
        external_id=conversation.external_id,
        provider=provider,
        status="received",
        metadata={
            **conversation.metadata,
            "sender_phone": conversation.sender_phone,
        },
    )

    if not inbound_message.get("created", True):
        return ControlledConversationResponse(
            handled=False,
            mode="ai_active",
            reply=None,
            patient_id=inbound_message.get("patient_id"),
            requires_human=False,
            actions=[],
            metadata={
                "duplicate_message": True,
                "thread_id": thread["id"],
                "inbound_message_id": inbound_message["id"],
            },
        )

    thread = await update_conversation_thread_after_message(
        cur=cur,
        thread_id=thread["id"],
        direction="inbound",
        patient_id=conversation.patient_id,
    )

    if (
        conversation.channel == "whatsapp"
        and provider == "evolution"
    ):
        confirmation_result = (
            await handle_appointment_confirmation_reply(
                clinic_id=conversation.clinic_id,
                patient_phone=conversation.sender_phone,
                reply_text=conversation.message,
            )
        )

        if confirmation_result is not None:
            confirmed_reminder = confirmation_result[
                "reminder"
            ]
            confirmed_appointment = confirmation_result[
                "appointment"
            ]

            confirmation_reply = (
                "Merci, votre rendez-vous est bien confirmé."
            )

            confirmed_patient_id = confirmed_reminder.get(
                "patient_id"
            )

            outbound_message = await create_conversation_message(
                cur=cur,
                clinic_id=conversation.clinic_id,
                thread_id=thread["id"],
                patient_id=confirmed_patient_id,
                channel=conversation.channel,
                direction="outbound",
                author_type="ai",
                message_type="text",
                body=confirmation_reply,
                provider=provider,
                status="prepared",
                requires_validation=False,
                metadata={
                    "intent": "appointment_confirmation",
                    "source": "appointment_confirmation",
                    "appointment_id": str(
                        confirmed_appointment["id"]
                    ),
                    "reminder_id": str(
                        confirmed_reminder["id"]
                    ),
                },
            )

            thread = await update_conversation_thread_after_message(
                cur=cur,
                thread_id=thread["id"],
                direction="outbound",
                patient_id=confirmed_patient_id,
            )

            return ControlledConversationResponse(
                handled=True,
                mode="ai_active",
                reply=confirmation_reply,
                patient_id=confirmed_patient_id,
                requires_human=False,
                actions=[],
                metadata={
                    "appointment_confirmation": True,
                    "appointment_id": str(
                        confirmed_appointment["id"]
                    ),
                    "reminder_id": str(
                        confirmed_reminder["id"]
                    ),
                    "thread_id": thread["id"],
                    "inbound_message_id": inbound_message[
                        "id"
                    ],
                    "outbound_message_id": outbound_message[
                        "id"
                    ],
                    "outbound_message_status": outbound_message[
                        "status"
                    ],
                    "unread_count": thread[
                        "unread_count"
                    ],
                },
            )

    control = await get_conversation_control(
        cur=cur,
        clinic_id=conversation.clinic_id,
        channel=conversation.channel,
        sender_phone=conversation.sender_phone,
    )

    mode = (
        control["mode"]
        if control is not None
        else "ai_active"
    )

    if not automatic_reply_allowed(control):
        patient_id = (
            control.get("patient_id")
            if control is not None
            else thread.get("patient_id")
        )

        return ControlledConversationResponse(
            handled=False,
            mode=mode,
            reply=None,
            patient_id=patient_id,
            requires_human=True,
            actions=[],
            metadata={
                "automatic_reply_blocked": True,
                "control_mode": mode,
                "thread_id": thread["id"],
                "inbound_message_id": inbound_message["id"],
                "unread_count": thread["unread_count"],
            },
        )

    effective_message = conversation.message
    debounced_message_count = 1
    debounce_degraded = False

    if provider == "evolution":
        # Le message entrant doit être visible immédiatement et
        # la transaction libérée avant la fenêtre de debounce.
        await cur.connection.commit()

        batch = await debounce_conversation_message(
            clinic_id=conversation.clinic_id,
            thread_id=thread["id"],
            message=conversation.message,
        )

        if not batch.should_process:
            return ControlledConversationResponse(
                handled=False,
                mode="ai_active",
                reply=None,
                patient_id=thread.get("patient_id"),
                requires_human=False,
                actions=[],
                metadata={
                    "debounced": True,
                    "debounce_superseded": True,
                    "thread_id": thread["id"],
                    "inbound_message_id": inbound_message["id"],
                    "unread_count": thread["unread_count"],
                },
            )

        effective_message = (
            batch.message
            if batch.message is not None
            else conversation.message
        )
        debounced_message_count = batch.message_count
        debounce_degraded = batch.degraded

    conversation_with_thread = conversation.model_copy(
        update={
            "message": effective_message,
            "metadata": {
                **conversation.metadata,
                "thread_id": str(thread["id"]),
                "debounced_message_count": debounced_message_count,
                "debounce_degraded": debounce_degraded,
            },
        },
    )

    result = await process_conversation(
        conversation_with_thread,
    )

    outbound_message = await create_conversation_message(
        cur=cur,
        clinic_id=conversation.clinic_id,
        thread_id=thread["id"],
        patient_id=result.patient_id,
        channel=conversation.channel,
        direction="outbound",
        author_type="ai",
        message_type="text",
        body=result.reply,
        provider=provider,
        status="prepared",
        requires_validation=False,
        metadata={
            "intent": result.intent,
            "source": "conversation_engine",
        },
    )

    thread = await update_conversation_thread_after_message(
        cur=cur,
        thread_id=thread["id"],
        direction="outbound",
        patient_id=result.patient_id,
    )

    response_metadata = {
        **result.metadata,
        "thread_id": thread["id"],
        "inbound_message_id": inbound_message["id"],
        "outbound_message_id": outbound_message["id"],
        "outbound_message_status": outbound_message["status"],
        "unread_count": thread["unread_count"],
    }

    return ControlledConversationResponse(
        handled=True,
        mode="ai_active",
        intent=result.intent,
        reply=result.reply,
        patient_id=result.patient_id,
        requires_human=result.requires_human,
        actions=result.actions,
        metadata=response_metadata,
    )


__all__ = [
    "optional_metadata_string",
    "process_controlled_conversation",
]
