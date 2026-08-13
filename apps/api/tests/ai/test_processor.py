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
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

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

    orchestration = SimpleNamespace(
        intent="reschedule_appointment",
        normalized_message="Je voudrais déplacer mon rendez-vous",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

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
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
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
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

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

    interpretation = SimpleNamespace(
        intent="unknown",
        treatment_text=None,
        practitioner_text=None,
        date_text="jeudi",
        time_text=None,
        selected_slot_index=None,
        confidence=0.9,
        needs_clarification=False,
        clarification_field="none",
    )

    orchestration = SimpleNamespace(
        intent="unknown",
        normalized_message="Finalement jeudi",
        interpretation=interpretation,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

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
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
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
        thread_id=None,
        session_id=None,
    )

    confirmation_mock.assert_not_awaited()


def test_booking_confirmation_correction_routes_to_time_response(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

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

    interpretation = SimpleNamespace(
        intent="unknown",
        treatment_text=None,
        practitioner_text=None,
        date_text=None,
        time_text="17h",
        selected_slot_index=None,
        confidence=0.9,
        needs_clarification=False,
        clarification_field="none",
    )

    orchestration = SimpleNamespace(
        intent="unknown",
        normalized_message="Finalement à 17h",
        interpretation=interpretation,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

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
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
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
        thread_id=None,
        session_id=None,
    )

    confirmation_mock.assert_not_awaited()


def test_booking_confirmation_correction_routes_to_practitioner_response(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Finalement avec le Dr Martin",
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

    interpretation = SimpleNamespace(
        intent="unknown",
        treatment_text=None,
        practitioner_text="Dr Martin",
        date_text=None,
        time_text=None,
        selected_slot_index=None,
        confidence=0.9,
        needs_clarification=False,
        clarification_field="none",
    )

    orchestration = SimpleNamespace(
        intent="unknown",
        normalized_message="Finalement avec le Dr Martin",
        interpretation=interpretation,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    practitioner_response_mock = AsyncMock(
        return_value=ConversationResult(
            intent="book_appointment",
            patient_id=patient_id,
            reply="Très bien, avec le Dr Martin.",
        )
    )

    confirmation_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        practitioner_response_mock,
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

    practitioner_response_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel=conversation.channel,
        patient=patient,
        message="Finalement avec le Dr Martin",
        current_context=context,
        thread_id=None,
        session_id=None,
    )

    confirmation_mock.assert_not_awaited()


def test_booking_confirmation_multiple_correction_routes_to_date_response(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Finalement jeudi à 17h",
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

    interpretation = SimpleNamespace(
        intent="unknown",
        treatment_text=None,
        practitioner_text=None,
        date_text="jeudi",
        time_text="17h",
        selected_slot_index=None,
        confidence=0.9,
        needs_clarification=False,
        clarification_field="none",
    )

    orchestration = SimpleNamespace(
        intent="unknown",
        normalized_message="Finalement jeudi à 17h",
        interpretation=interpretation,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    date_response_mock = AsyncMock(
        return_value=ConversationResult(
            intent="book_appointment",
            patient_id=patient_id,
            reply="Très bien, jeudi à 17h.",
        )
    )

    time_response_mock = AsyncMock()
    confirmation_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_date_response",
        date_response_mock,
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

    date_response_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel="web",
        patient=patient,
        message="Finalement jeudi à 17h",
        current_context=context,
        thread_id=None,
        session_id=None,
    )

    time_response_mock.assert_not_awaited()
    confirmation_mock.assert_not_awaited()


def test_thanks_interrupts_waiting_for_time(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Merci beaucoup",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    conversation_state = {
        "state": "waiting_for_time",
        "context": {
            "intent": "book_appointment",
        },
    }

    orchestration = SimpleNamespace(
        intent="thanks",
        normalized_message="Merci beaucoup",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    thanks_mock = Mock(
        return_value=ConversationResult(
            intent="thanks",
            patient_id=patient_id,
            reply="Avec plaisir.",
        )
    )

    booking_time_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )

    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )

    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )

    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )

    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )

    monkeypatch.setattr(
        processor,
        "handle_thanks",
        thanks_mock,
    )

    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        booking_time_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "thanks"

    thanks_mock.assert_called_once_with(patient)
    booking_time_mock.assert_not_awaited()



def test_goodbye_interrupts_waiting_for_time(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Bonne journée",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    conversation_state = {
        "state": "waiting_for_time",
        "context": {
            "intent": "book_appointment",
        },
    }

    orchestration = SimpleNamespace(
        intent="goodbye",
        normalized_message="Bonne journée",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    goodbye_mock = Mock(
        return_value=ConversationResult(
            intent="goodbye",
            patient_id=patient_id,
            reply="Au revoir.",
        )
    )

    booking_time_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "handle_goodbye",
        goodbye_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        booking_time_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "goodbye"
    goodbye_mock.assert_called_once_with(patient)
    booking_time_mock.assert_not_awaited()


def test_human_handoff_interrupts_waiting_for_time(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message=(
            "D'après ma radio, est-ce que je peux "
            "refaire un blanchiment ?"
        ),
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    conversation_state = {
        "state": "waiting_for_time",
        "context": {
            "intent": "book_appointment",
        },
    }

    orchestration = SimpleNamespace(
        intent="human_handoff",
        normalized_message="Blanchiment",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    booking_time_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        booking_time_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "human_handoff"
    assert result.requires_human is True
    booking_time_mock.assert_not_awaited()


def test_dental_information_interrupts_waiting_for_time(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Est-ce que le blanchiment fragilise les dents ?",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    conversation_state = {
        "state": "waiting_for_time",
        "context": {
            "intent": "book_appointment",
            "history": [],
        },
    }

    orchestration = SimpleNamespace(
        intent="dental_information",
        normalized_message="Blanchiment",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    knowledge_mock = AsyncMock(
        return_value=(
            "Le blanchiment professionnel ne fragilise généralement "
            "pas les dents, mais peut provoquer une sensibilité temporaire."
        )
    )

    booking_time_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "generate_knowledge_fallback",
        knowledge_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        booking_time_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result.intent == "dental_information"
    assert result.requires_human is False
    assert result.metadata["reply_source"] == "knowledge_fallback"

    knowledge_mock.assert_awaited_once_with(
        user_message=conversation.message,
        conversation_context=None,
        clinical_context=None,
    )
    booking_time_mock.assert_not_awaited()


def test_process_conversation_passes_patient_memory_to_chat_model(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="web",
        sender_phone="+213555123456",
        message="Merci beaucoup",
    )

    core_result = ConversationResult(
        intent="thanks",
        patient_id=patient_id,
        reply="Avec plaisir.",
    )

    patient_context = SimpleNamespace(
        patient_name="Farid Houait",
        summary=(
            "Le patient préfère les rendez-vous le vendredi "
            "après 17h avec le Dr Martin."
        ),
        preferences={
            "preferred_day": "vendredi",
            "preferred_time": "après 17h",
            "preferred_practitioner": "Dr Martin",
        },
    )

    captured_contexts = []

    async def fake_generate_natural_reply(context):
        captured_contexts.append(context)
        return context.business_reply

    monkeypatch.setattr(
        processor,
        "_process_conversation_core",
        AsyncMock(return_value=core_result),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "generate_natural_reply",
        fake_generate_natural_reply,
    )
    monkeypatch.setattr(
        processor,
        "append_conversation_turn",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        processor,
        "_summarize_history_if_needed",
        AsyncMock(return_value=None),
    )

    result = asyncio.run(
        processor.process_conversation(conversation)
    )

    assert result == core_result
    assert len(captured_contexts) == 1

    chat_context = captured_contexts[0]

    assert chat_context.patient_name == "Farid Houait"
    assert chat_context.patient_summary == patient_context.summary
    assert (
        chat_context.patient_preferences
        == patient_context.preferences
    )
    assert chat_context.intent == "thanks"
    assert chat_context.business_reply == "Avec plaisir."


def test_process_conversation_activates_and_resets_session(
    monkeypatch,
):
    import asyncio
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    conversation = ConversationInput(
        clinic_id=uuid4(),
        channel="phone",
        sender_phone="+213555123456",
        message="Bonjour",
        session_id="call-test-session-001",
    )

    expected_result = ConversationResult(
        intent="greeting",
        reply="Bonjour.",
    )

    session_token = object()

    set_session_mock = Mock(
        return_value=session_token,
    )
    reset_session_mock = Mock()
    active_processor_mock = AsyncMock(
        return_value=expected_result,
    )

    monkeypatch.setattr(
        processor,
        "set_conversation_session",
        set_session_mock,
    )
    monkeypatch.setattr(
        processor,
        "reset_conversation_session",
        reset_session_mock,
    )
    monkeypatch.setattr(
        processor,
        "_process_conversation_with_active_session",
        active_processor_mock,
    )

    result = asyncio.run(
        processor.process_conversation(conversation)
    )

    assert result == expected_result

    set_session_mock.assert_called_once_with(
        "call-test-session-001",
    )
    active_processor_mock.assert_awaited_once_with(
        conversation,
    )
    reset_session_mock.assert_called_once_with(
        session_token,
    )


def test_waiting_for_time_ignores_preference_update_interrupt(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="phone",
        sender_phone="+213555123456",
        message="17h30",
        session_id="call-preference-test-001",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    context = {
        "intent": "book_appointment",
        "requested_date_text": "vendredi",
        "requested_time_text": "après 17h",
        "suggested_slots": [],
    }

    conversation_state = {
        "state": "waiting_for_time",
        "context": context,
    }

    orchestration = SimpleNamespace(
        intent="preference_update",
        normalized_message="après 17h",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={
            "preferred_day": "vendredi",
            "preferred_time": "après 17h",
        },
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    expected_result = ConversationResult(
        intent="book_appointment",
        patient_id=patient_id,
        reply="Le créneau de 17h30 est disponible.",
    )

    booking_time_mock = AsyncMock(
        return_value=expected_result,
    )
    save_state_mock = AsyncMock()

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=conversation_state),
    )
    monkeypatch.setattr(
        processor,
        "save_conversation_state",
        save_state_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_booking_time_response",
        booking_time_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result == expected_result

    booking_time_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        channel="phone",
        patient=patient,
        message="17h30",
        current_context=context,
        thread_id=None,
        session_id="call-preference-test-001",
    )

    save_state_mock.assert_not_awaited()


def test_new_named_session_is_initialized_as_idle(
    monkeypatch,
):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4

    from app.ai import processor
    from app.ai.schemas import (
        ConversationInput,
        ConversationResult,
    )

    clinic_id = uuid4()
    patient_id = uuid4()

    conversation = ConversationInput(
        clinic_id=clinic_id,
        channel="phone",
        sender_phone="+213555123456",
        message="Bonjour",
        session_id="call-new-session-001",
    )

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
    }

    initialized_state = {
        "state": "idle",
        "context": {},
        "session_id": "call-new-session-001",
    }

    orchestration = SimpleNamespace(
        intent="greeting",
        normalized_message="Bonjour",
        interpretation=None,
    )

    patient_context = SimpleNamespace(
        preferences={},
        summary=None,
        patient_name="Patient Test",
        medical_history=[],
        recent_documents=[],
        notes=[],
    )

    expected_result = ConversationResult(
        intent="greeting",
        patient_id=patient_id,
        reply="Bonjour Patient Test.",
    )

    save_state_mock = AsyncMock(
        return_value=initialized_state,
    )
    greeting_mock = Mock(
        return_value=expected_result,
    )

    monkeypatch.setattr(
        processor,
        "find_patient_by_phone",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        processor,
        "_remember_explicit_preferences",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr(
        processor,
        "build_patient_context",
        AsyncMock(return_value=patient_context),
    )
    monkeypatch.setattr(
        processor,
        "orchestrate_conversation_message",
        AsyncMock(return_value=orchestration),
    )
    monkeypatch.setattr(
        processor,
        "get_conversation_state",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        processor,
        "save_conversation_state",
        save_state_mock,
    )
    monkeypatch.setattr(
        processor,
        "handle_greeting",
        greeting_mock,
    )

    result = asyncio.run(
        processor._process_conversation_core(conversation)
    )

    assert result == expected_result

    save_state_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        patient_id=patient_id,
        channel="phone",
        state="idle",
        context={},
        session_id="call-new-session-001",
    )

    greeting_mock.assert_called_once_with(patient)

