from app.ai.processor import _has_new_explicit_intent


def test_explicit_rescheduling_intent_restarts_active_workflow():
    assert _has_new_explicit_intent("reschedule_appointment") is True


def test_explicit_booking_intent_restarts_active_workflow():
    assert _has_new_explicit_intent("book_appointment") is True


def test_explicit_cancellation_intent_restarts_active_workflow():
    assert _has_new_explicit_intent("cancel_appointment") is True


def test_non_interruptible_intent_does_not_restart_active_workflow():
    assert _has_new_explicit_intent("unknown") is False


def test_explicit_rescheduling_restarts_existing_rescheduling_workflow(
    monkeypatch,
):
    import asyncio
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import ConversationInput, ConversationResult

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Je voudrais déplacer mon rendez-vous",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    conversation_state = {
        "state": "waiting_for_reschedule_time",
        "context": {
            "intent": "reschedule_appointment",
        },
    }

    find_patient_mock = AsyncMock(return_value=patient)
    get_state_mock = AsyncMock(return_value=conversation_state)
    rescheduling_mock = AsyncMock(
        return_value=ConversationResult(
            intent="reschedule_appointment",
            patient_id=patient_id,
            reply="Quel rendez-vous souhaitez-vous déplacer ?",
        )
    )
    time_response_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "detect_intent",
        lambda message: "reschedule_appointment",
    )
    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        find_patient_mock,
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        get_state_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_rescheduling",
        rescheduling_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_rescheduling_time_response",
        time_response_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "reschedule_appointment"

    rescheduling_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel="web",
        patient=patient,
        message="Je voudrais déplacer mon rendez-vous",
    )
    time_response_mock.assert_not_awaited()
