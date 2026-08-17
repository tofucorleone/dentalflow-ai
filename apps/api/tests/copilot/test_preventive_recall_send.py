import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import app.copilot.router as copilot_router
from app.copilot.router import send_recall_proposal
from app.copilot.schemas import RecallSendRequest


def test_preventive_recall_send_request_without_slot():
    draft_id = uuid4()
    patient_id = uuid4()

    payload = RecallSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        message="Bonjour, souhaitez-vous prendre rendez-vous ?",
    )

    assert payload.draft_id == draft_id
    assert payload.patient_id == patient_id
    assert payload.appointment_id is None
    assert payload.practitioner_id is None
    assert payload.treatment_id is None
    assert payload.start_at is None
    assert payload.end_at is None


def test_slot_recall_send_request_remains_compatible():
    draft_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()
    practitioner_id = uuid4()

    payload = RecallSendRequest.model_validate(
        {
            "draft_id": str(draft_id),
            "patient_id": str(patient_id),
            "appointment_id": str(appointment_id),
            "practitioner_id": str(practitioner_id),
            "treatment_id": None,
            "start_at": "2026-08-20T10:00:00+00:00",
            "end_at": "2026-08-20T10:30:00+00:00",
            "message": "Un créneau est disponible.",
        }
    )

    assert payload.appointment_id == appointment_id
    assert payload.practitioner_id == practitioner_id
    assert payload.start_at is not None
    assert payload.end_at is not None


class FakeCursor:
    def __init__(self, fetchone_results=None):
        self.fetchone_results = list(
            fetchone_results or []
        )
        self.executed = []

    async def execute(self, query, params):
        self.executed.append((query, params))

    async def fetchone(self):
        if not self.fetchone_results:
            return None

        return self.fetchone_results.pop(0)

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commit_calls = 0

    def cursor(self):
        return self._cursor

    async def commit(self):
        self.commit_calls += 1


def test_preventive_recall_send_does_not_start_booking(
    monkeypatch,
):
    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    draft_id = uuid4()
    thread_id = uuid4()
    prepared_message_id = uuid4()

    first_cursor = FakeCursor(
        fetchone_results=[
            {
                "id": thread_id,
            },
            {
                "id": draft_id,
            },
        ]
    )
    second_cursor = FakeCursor()

    connections = [
        FakeConnection(first_cursor),
        FakeConnection(second_cursor),
    ]

    @asynccontextmanager
    async def fake_connection():
        if not connections:
            raise AssertionError(
                "Connexion DB inattendue."
            )

        yield connections.pop(0)

    prepared_thread = {
        "id": thread_id,
        "provider_instance": "clinic-test",
        "sender_phone": "+213555000001",
    }

    prepared_message = {
        "id": prepared_message_id,
        "body": (
            "Bonjour, souhaitez-vous prendre "
            "rendez-vous ?"
        ),
    }

    sent_message = {
        **prepared_message,
        "status": "sent",
        "external_id": "provider-message-123",
    }

    prepare_message_mock = AsyncMock(
        return_value=(
            prepared_thread,
            prepared_message,
        )
    )

    send_mock = AsyncMock(
        return_value={
            "external_id": "provider-message-123",
            "response": {
                "accepted": True,
            },
        }
    )

    mark_sent_mock = AsyncMock(
        return_value=sent_message
    )
    save_state_mock = AsyncMock()
    audit_mock = AsyncMock()
    publish_mock = AsyncMock(return_value=1)

    monkeypatch.setattr(
        copilot_router,
        "connection",
        fake_connection,
    )
    monkeypatch.setattr(
        copilot_router,
        "prepare_human_message",
        prepare_message_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "send_evolution_text_message",
        send_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "mark_human_message_sent",
        mark_sent_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "save_conversation_state",
        save_state_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "record_copilot_audit_event",
        audit_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "publish_conversation_event",
        publish_mock,
    )

    payload = RecallSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        message=prepared_message["body"],
    )

    result = asyncio.run(
        send_recall_proposal(
            payload=payload,
            current_clinic=clinic_id,
            user={
                "id": user_id,
                "full_name": "Utilisateur Test",
            },
        )
    )

    assert result["status"] == "sent"
    assert result["draft_id"] == draft_id
    assert result["thread_id"] == thread_id
    assert result["waiting_for_confirmation"] is False
    assert result["message"] == sent_message

    save_state_mock.assert_not_awaited()

    prepare_message_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        thread_id=thread_id,
        user_id=user_id,
        body=prepared_message["body"],
    )

    send_mock.assert_awaited_once_with(
        instance="clinic-test",
        sender_phone="+213555000001",
        text=prepared_message["body"],
    )

    mark_sent_mock.assert_awaited_once_with(
        cur=second_cursor,
        clinic_id=clinic_id,
        message_id=prepared_message_id,
        external_id="provider-message-123",
        provider_response={
            "accepted": True,
        },
    )

    audit_mock.assert_awaited_once()

    audit_call = audit_mock.await_args.kwargs

    assert audit_call["action_type"] == (
        "recall_proposal_sent"
    )
    assert audit_call["result"] == "success"
    assert audit_call["entity_type"] == (
        "communication_event"
    )
    assert audit_call["entity_id"] == draft_id
    assert audit_call["after_data"] == {
        "status": "sent",
    }

    publish_mock.assert_awaited_once_with(
        clinic_id=clinic_id,
        event_type="conversation.message.sent",
        data={
            "thread_id": str(thread_id),
            "message": sent_message,
        },
    )

    assert len(first_cursor.executed) == 2

    draft_query, draft_params = (
        first_cursor.executed[1]
    )

    assert (
        "appointment_id IS NOT DISTINCT FROM %s"
        in draft_query
    )
    assert draft_params[-1] is None

    assert len(second_cursor.executed) == 1

    update_query, update_params = (
        second_cursor.executed[0]
    )

    assert "UPDATE communication_events" in update_query
    assert '"sent"' in update_query
    assert update_params == (
        "provider-message-123",
        draft_id,
        clinic_id,
    )


def test_preventive_recall_creates_thread_when_missing(
    monkeypatch,
):
    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    draft_id = uuid4()
    thread_id = uuid4()
    prepared_message_id = uuid4()

    first_cursor = FakeCursor(
        fetchone_results=[
            # Aucun thread ouvert existant.
            None,
            # Draft toujours disponible.
            {
                "id": draft_id,
            },
            # Patient.
            {
                "phone": "+213600000000",
            },
            # Intégration Evolution active.
            {
                "provider_instance": "agence",
            },
        ]
    )
    second_cursor = FakeCursor()

    connections = [
        FakeConnection(first_cursor),
        FakeConnection(second_cursor),
    ]

    @asynccontextmanager
    async def fake_connection():
        if not connections:
            raise AssertionError(
                "Connexion DB inattendue."
            )

        yield connections.pop(0)

    created_thread = {
        "id": thread_id,
        "clinic_id": clinic_id,
        "patient_id": patient_id,
        "channel": "whatsapp",
        "status": "open",
        "provider": "evolution",
        "provider_instance": "agence",
        "sender_phone": "+213600000000",
    }

    prepared_message = {
        "id": prepared_message_id,
        "body": (
            "Bonjour, souhaitez-vous prendre "
            "rendez-vous ?"
        ),
    }

    sent_message = {
        **prepared_message,
        "status": "sent",
        "external_id": "provider-message-456",
    }

    get_or_create_mock = AsyncMock(
        return_value=created_thread
    )
    prepare_message_mock = AsyncMock(
        return_value=(
            created_thread,
            prepared_message,
        )
    )
    send_mock = AsyncMock(
        return_value={
            "external_id": "provider-message-456",
            "response": {
                "accepted": True,
            },
        }
    )
    mark_sent_mock = AsyncMock(
        return_value=sent_message
    )
    save_state_mock = AsyncMock()
    audit_mock = AsyncMock()
    publish_mock = AsyncMock(return_value=1)

    monkeypatch.setattr(
        copilot_router,
        "connection",
        fake_connection,
    )
    monkeypatch.setattr(
        copilot_router,
        "get_or_create_conversation_thread",
        get_or_create_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "prepare_human_message",
        prepare_message_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "send_evolution_text_message",
        send_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "mark_human_message_sent",
        mark_sent_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "save_conversation_state",
        save_state_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "record_copilot_audit_event",
        audit_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "publish_conversation_event",
        publish_mock,
    )

    payload = RecallSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        message=prepared_message["body"],
    )

    result = asyncio.run(
        send_recall_proposal(
            payload=payload,
            current_clinic=clinic_id,
            user={
                "id": user_id,
                "full_name": "Utilisateur Test",
            },
        )
    )

    assert result["status"] == "sent"
    assert result["thread_id"] == thread_id
    assert result["waiting_for_confirmation"] is False

    get_or_create_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        patient_id=patient_id,
        channel="whatsapp",
        sender_phone="+213600000000",
        provider="evolution",
        provider_instance="agence",
        external_thread_id=None,
    )

    prepare_message_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        thread_id=thread_id,
        user_id=user_id,
        body=prepared_message["body"],
    )

    send_mock.assert_awaited_once_with(
        instance="agence",
        sender_phone="+213600000000",
        text=prepared_message["body"],
    )

    save_state_mock.assert_not_awaited()

    assert len(first_cursor.executed) == 4

    thread_query = first_cursor.executed[0][0]
    draft_query = first_cursor.executed[1][0]
    patient_query = first_cursor.executed[2][0]
    integration_query = first_cursor.executed[3][0]

    assert "FROM conversation_threads" in thread_query

    assert (
        "appointment_id IS NOT DISTINCT FROM %s"
        in draft_query
    )

    assert "FROM patients" in patient_query

    assert "FROM clinic_integrations" in integration_query
    assert (
        "LOWER(BTRIM(provider)) = 'evolution'"
        in integration_query
    )

    audit_call = audit_mock.await_args.kwargs

    assert audit_call["entity_type"] == (
        "communication_event"
    )
    assert audit_call["entity_id"] == draft_id
