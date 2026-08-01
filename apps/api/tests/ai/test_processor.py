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


def test_booking_confirmation_correction_routes_to_date_response(
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
        message="Finalement jeudi",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    context = {
        "intent": "book_appointment",
        "requested_date_text": "mardi",
        "requested_time_text": "15h00",
        "practitioner_id": str(uuid4()),
        "start_at": "2026-08-04T15:00:00+01:00",
        "end_at": "2026-08-04T15:30:00+01:00",
    }

    conversation_state = {
        "state": "waiting_for_confirmation",
        "context": context,
    }

    find_patient_mock = AsyncMock(return_value=patient)
    get_state_mock = AsyncMock(return_value=conversation_state)

    date_response_mock = AsyncMock(
        return_value=ConversationResult(
            intent="book_appointment",
            patient_id=patient_id,
            reply="Très bien, vous souhaitez venir jeudi.",
        )
    )
    confirmation_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "detect_intent",
        lambda message: "unknown",
    )
    monkeypatch.setattr(
        processor,
        "find_treatment_in_message",
        AsyncMock(return_value=None),
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
        "handle_booking_date_response",
        date_response_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_confirmation_response",
        confirmation_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "book_appointment"

    date_response_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel="web",
        patient=patient,
        message="Finalement jeudi",
        current_context=context,
    )
    confirmation_mock.assert_not_awaited()


def test_booking_confirmation_correction_routes_to_time_response(
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
        message="Finalement à 17h",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    context = {
        "intent": "book_appointment",
        "requested_date_text": "mardi",
        "requested_time_text": "15h00",
        "practitioner_id": str(uuid4()),
        "start_at": "2026-08-04T15:00:00+01:00",
        "end_at": "2026-08-04T15:30:00+01:00",
    }

    conversation_state = {
        "state": "waiting_for_confirmation",
        "context": context,
    }

    find_patient_mock = AsyncMock(return_value=patient)
    get_state_mock = AsyncMock(return_value=conversation_state)

    time_response_mock = AsyncMock(
        return_value=ConversationResult(
            intent="book_appointment",
            patient_id=patient_id,
            reply="Très bien, vous souhaitez venir à 17h.",
        )
    )
    confirmation_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "detect_intent",
        lambda message: "unknown",
    )
    monkeypatch.setattr(
        processor,
        "find_treatment_in_message",
        AsyncMock(return_value=None),
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
        "handle_booking_time_response",
        time_response_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_confirmation_response",
        confirmation_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "book_appointment"

    time_response_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel="web",
        patient=patient,
        message="Finalement à 17h",
        current_context=context,
    )
    confirmation_mock.assert_not_awaited()
