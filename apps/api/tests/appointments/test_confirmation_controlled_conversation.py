import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

from app.ai import controlled_conversation
from app.ai.schemas import ConversationInput


CLINIC_ID = UUID("576a0895-f0f1-4e4f-b78c-c1d81d2da562")
PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
THREAD_ID = UUID("22222222-2222-2222-2222-222222222222")
MESSAGE_ID = UUID("33333333-3333-3333-3333-333333333333")
REMINDER_ID = UUID("44444444-4444-4444-4444-444444444444")
APPOINTMENT_ID = UUID("55555555-5555-5555-5555-555555555555")


def test_evolution_oui_confirmation_short_circuits_normal_conversation(
    monkeypatch,
):
    thread = {
        "id": THREAD_ID,
        "patient_id": PATIENT_ID,
        "unread_count": 0,
    }

    updated_thread = {
        **thread,
        "unread_count": 1,
    }

    inbound_message = {
        "id": MESSAGE_ID,
        "patient_id": PATIENT_ID,
        "created": True,
    }

    outbound_message = {
        "id": UUID(
            "66666666-6666-6666-6666-666666666666"
        ),
        "patient_id": PATIENT_ID,
        "status": "prepared",
        "created": True,
    }

    confirmation_result = {
        "reminder": {
            "id": REMINDER_ID,
            "patient_id": PATIENT_ID,
        },
        "appointment": {
            "id": APPOINTMENT_ID,
        },
    }

    get_thread_mock = AsyncMock(return_value=thread)
    create_message_mock = AsyncMock(
        side_effect=[
            inbound_message,
            outbound_message,
        ]
    )
    update_thread_mock = AsyncMock(
        side_effect=[
            updated_thread,
            updated_thread,
        ]
    )
    confirmation_mock = AsyncMock(return_value=confirmation_result)

    control_mock = AsyncMock()
    debounce_mock = AsyncMock()
    processor_mock = AsyncMock()

    monkeypatch.setattr(
        controlled_conversation,
        "get_or_create_conversation_thread",
        get_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "create_conversation_message",
        create_message_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "update_conversation_thread_after_message",
        update_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "handle_appointment_confirmation_reply",
        confirmation_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "get_conversation_control",
        control_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "debounce_conversation_message",
        debounce_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "process_conversation",
        processor_mock,
    )

    connection = SimpleNamespace(
        commit=AsyncMock(),
    )
    cur = SimpleNamespace(
        connection=connection,
    )

    conversation = ConversationInput(
        clinic_id=CLINIC_ID,
        patient_id=PATIENT_ID,
        channel="whatsapp",
        sender_phone="+213542910065",
        message="OUI",
        external_id="evolution-message-001",
        metadata={
            "provider": "evolution",
            "provider_instance": "cabinet-demo",
        },
    )

    result = asyncio.run(
        controlled_conversation.process_controlled_conversation(
            cur=cur,
            conversation=conversation,
        )
    )

    assert result.handled is True
    assert (
        result.reply
        == "Merci, votre rendez-vous est bien confirmé."
    )
    assert result.intent is None
    assert result.requires_human is False
    assert result.metadata["appointment_confirmation"] is True
    assert result.metadata["appointment_id"] == str(APPOINTMENT_ID)
    assert result.metadata["reminder_id"] == str(REMINDER_ID)
    assert result.metadata["thread_id"] == THREAD_ID
    assert result.metadata["inbound_message_id"] == MESSAGE_ID
    assert (
        result.metadata["outbound_message_id"]
        == outbound_message["id"]
    )
    assert (
        result.metadata["outbound_message_status"]
        == "prepared"
    )
    assert result.metadata["unread_count"] == 1

    confirmation_mock.assert_awaited_once_with(
        clinic_id=CLINIC_ID,
        patient_phone="+213542910065",
        reply_text="OUI",
    )

    assert create_message_mock.await_count == 2

    outbound_call = create_message_mock.await_args_list[1]

    assert outbound_call.kwargs["clinic_id"] == CLINIC_ID
    assert outbound_call.kwargs["thread_id"] == THREAD_ID
    assert outbound_call.kwargs["patient_id"] == PATIENT_ID
    assert outbound_call.kwargs["channel"] == "whatsapp"
    assert outbound_call.kwargs["direction"] == "outbound"
    assert outbound_call.kwargs["author_type"] == "ai"
    assert outbound_call.kwargs["message_type"] == "text"
    assert (
        outbound_call.kwargs["body"]
        == "Merci, votre rendez-vous est bien confirmé."
    )
    assert outbound_call.kwargs["provider"] == "evolution"
    assert outbound_call.kwargs["status"] == "prepared"
    assert (
        outbound_call.kwargs["requires_validation"]
        is False
    )

    assert update_thread_mock.await_count == 2

    outbound_thread_call = (
        update_thread_mock.await_args_list[1]
    )

    assert (
        outbound_thread_call.kwargs["thread_id"]
        == THREAD_ID
    )
    assert (
        outbound_thread_call.kwargs["direction"]
        == "outbound"
    )
    assert (
        outbound_thread_call.kwargs["patient_id"]
        == PATIENT_ID
    )

    control_mock.assert_not_awaited()
    debounce_mock.assert_not_awaited()
    processor_mock.assert_not_awaited()


def test_duplicate_evolution_message_does_not_confirm_or_process(
    monkeypatch,
):
    thread = {
        "id": THREAD_ID,
        "patient_id": PATIENT_ID,
        "unread_count": 1,
    }

    duplicate_inbound_message = {
        "id": MESSAGE_ID,
        "patient_id": PATIENT_ID,
        "created": False,
    }

    get_thread_mock = AsyncMock(return_value=thread)
    create_message_mock = AsyncMock(
        return_value=duplicate_inbound_message
    )

    update_thread_mock = AsyncMock()
    confirmation_mock = AsyncMock()
    control_mock = AsyncMock()
    debounce_mock = AsyncMock()
    processor_mock = AsyncMock()

    monkeypatch.setattr(
        controlled_conversation,
        "get_or_create_conversation_thread",
        get_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "create_conversation_message",
        create_message_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "update_conversation_thread_after_message",
        update_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "handle_appointment_confirmation_reply",
        confirmation_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "get_conversation_control",
        control_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "debounce_conversation_message",
        debounce_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "process_conversation",
        processor_mock,
    )

    connection = SimpleNamespace(
        commit=AsyncMock(),
    )
    cur = SimpleNamespace(
        connection=connection,
    )

    conversation = ConversationInput(
        clinic_id=CLINIC_ID,
        patient_id=PATIENT_ID,
        channel="whatsapp",
        sender_phone="+213542910065",
        message="OUI",
        external_id="evolution-message-duplicate",
        metadata={
            "provider": "evolution",
            "provider_instance": "cabinet-demo",
        },
    )

    result = asyncio.run(
        controlled_conversation.process_controlled_conversation(
            cur=cur,
            conversation=conversation,
        )
    )

    assert result.handled is False
    assert result.reply is None
    assert result.requires_human is False
    assert result.metadata["duplicate_message"] is True
    assert result.metadata["thread_id"] == THREAD_ID
    assert result.metadata["inbound_message_id"] == MESSAGE_ID

    update_thread_mock.assert_not_awaited()
    confirmation_mock.assert_not_awaited()
    control_mock.assert_not_awaited()
    debounce_mock.assert_not_awaited()
    processor_mock.assert_not_awaited()


def test_evolution_non_confirmation_continues_normal_conversation(
    monkeypatch,
):
    thread = {
        "id": THREAD_ID,
        "patient_id": PATIENT_ID,
        "unread_count": 0,
    }

    updated_thread = {
        **thread,
        "unread_count": 1,
    }

    inbound_message = {
        "id": MESSAGE_ID,
        "patient_id": PATIENT_ID,
        "created": True,
    }

    get_thread_mock = AsyncMock(return_value=thread)

    outbound_message = {
        "id": UUID("66666666-6666-6666-6666-666666666666"),
        "status": "prepared",
    }

    create_message_mock = AsyncMock(
        side_effect=[
            inbound_message,
            outbound_message,
        ]
    )

    update_thread_mock = AsyncMock(return_value=updated_thread)

    confirmation_mock = AsyncMock(return_value=None)

    control_mock = AsyncMock(
        return_value={
            "mode": "ai_active",
        }
    )

    debounce_mock = AsyncMock(
        return_value=SimpleNamespace(
            should_process=True,
            message="NON",
            message_count=1,
            degraded=False,
        )
    )

    processor_result = SimpleNamespace(
        intent="unknown",
        reply="Je peux vous aider avec votre demande.",
        patient_id=PATIENT_ID,
        requires_human=False,
        actions=[],
        metadata={},
    )

    processor_mock = AsyncMock(return_value=processor_result)

    monkeypatch.setattr(
        controlled_conversation,
        "get_or_create_conversation_thread",
        get_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "create_conversation_message",
        create_message_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "update_conversation_thread_after_message",
        update_thread_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "handle_appointment_confirmation_reply",
        confirmation_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "get_conversation_control",
        control_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "debounce_conversation_message",
        debounce_mock,
    )
    monkeypatch.setattr(
        controlled_conversation,
        "process_conversation",
        processor_mock,
    )

    connection = SimpleNamespace(
        commit=AsyncMock(),
    )
    cur = SimpleNamespace(
        connection=connection,
    )

    conversation = ConversationInput(
        clinic_id=CLINIC_ID,
        patient_id=PATIENT_ID,
        channel="whatsapp",
        sender_phone="+213542910065",
        message="NON",
        external_id="evolution-message-non-confirmation",
        metadata={
            "provider": "evolution",
            "provider_instance": "cabinet-demo",
        },
    )

    result = asyncio.run(
        controlled_conversation.process_controlled_conversation(
            cur=cur,
            conversation=conversation,
        )
    )

    confirmation_mock.assert_awaited_once_with(
        clinic_id=CLINIC_ID,
        patient_phone="+213542910065",
        reply_text="NON",
    )

    processor_mock.assert_awaited_once()

    assert result.metadata.get("appointment_confirmation") is not True
