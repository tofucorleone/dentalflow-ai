from fastapi.routing import APIRoute

from app.auth import current_user
from app.copilot.router import router
from app.deps import authenticated_clinic_id


def _route():
    return next(
        item
        for item in router.routes
        if isinstance(item, APIRoute)
        and item.path == "/copilot/appointment-message-drafts"
        and "POST" in item.methods
    )


def test_appointment_message_draft_route_is_protected():
    route = _route()

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert current_user in dependency_calls
    assert authenticated_clinic_id in dependency_calls


def test_appointment_message_draft_route_uses_expected_response_model():
    route = _route()

    assert route.status_code == 201
    assert (
        route.response_model.__name__
        == "AppointmentMessageDraftResponse"
    )


def test_appointment_message_send_route_is_registered():
    routes = [
        item
        for item in router.routes
        if getattr(item, "path", None)
        == "/copilot/appointment-message-drafts/send"
    ]

    assert len(routes) == 1

    route = routes[0]

    assert "POST" in route.methods
    assert route.status_code == 201


def test_appointment_message_send_happy_path(
    monkeypatch,
):
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from uuid import uuid4

    import app.copilot.router as copilot_router
    from app.copilot.schemas import (
        AppointmentMessageSendRequest,
    )

    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()
    draft_id = uuid4()
    thread_id = uuid4()
    prepared_message_id = uuid4()

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

    message = (
        "Bonjour, confirmez-vous votre "
        "rendez-vous demain ?"
    )

    prepared_thread = {
        "id": thread_id,
        "provider_instance": "clinic-test",
        "sender_phone": "+213555000001",
    }

    prepared_message = {
        "id": prepared_message_id,
        "body": message,
    }

    sent_message = {
        **prepared_message,
        "status": "sent",
        "external_id": "provider-message-456",
    }

    prepare_message_mock = AsyncMock(
        return_value=(
            prepared_thread,
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

    payload = AppointmentMessageSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        message_kind="pending_confirmation",
        message=message,
    )

    result = asyncio.run(
        copilot_router.send_appointment_message_draft_endpoint(
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
    assert result["message"] == sent_message

    # Un message de confirmation/no-show ne doit pas
    # démarrer un workflow conversationnel de réservation.
    save_state_mock.assert_not_awaited()

    prepare_message_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        thread_id=thread_id,
        user_id=user_id,
        body=message,
    )

    send_mock.assert_awaited_once_with(
        instance="clinic-test",
        sender_phone="+213555000001",
        text=message,
    )

    mark_sent_mock.assert_awaited_once_with(
        cur=second_cursor,
        clinic_id=clinic_id,
        message_id=prepared_message_id,
        external_id="provider-message-456",
        provider_response={
            "accepted": True,
        },
    )

    audit_mock.assert_awaited_once()

    audit_call = audit_mock.await_args.kwargs

    assert audit_call["action_type"] == (
        "appointment_message_sent"
    )
    assert audit_call["result"] == "success"
    assert audit_call["entity_type"] == (
        "communication_event"
    )
    assert audit_call["entity_id"] == draft_id
    assert audit_call["after_data"] == {
        "status": "sent",
        "message_kind": "pending_confirmation",
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
        "event_type = 'appointment_message_draft'"
        in draft_query
    )
    assert "payload->>'message_kind' = %s" in draft_query
    assert "payload->>'status' = 'draft'" in draft_query

    assert draft_params == (
        draft_id,
        clinic_id,
        patient_id,
        appointment_id,
        "pending_confirmation",
    )

    assert len(second_cursor.executed) == 3

    update_query, update_params = (
        second_cursor.executed[0]
    )

    reminder_query, reminder_params = (
        second_cursor.executed[1]
    )

    assert (
        "INSERT INTO appointment_confirmation_reminders"
        in reminder_query
    )
    assert "ON CONFLICT (appointment_id)" in reminder_query
    assert "DO UPDATE SET" in reminder_query
    assert "'sent'" in reminder_query

    assert reminder_params == (
        clinic_id,
        "clinic-test",
        "provider-message-456",
        appointment_id,
        clinic_id,
        patient_id,
    )

    task_state_query, task_state_params = (
        second_cursor.executed[2]
    )

    assert "copilot_task_states" in task_state_query

    assert task_state_params == (
        clinic_id,
        f"confirmation:{appointment_id}",
        "completed",
        None,
        None,
    )

    assert "UPDATE communication_events" in update_query
    assert '"sent"' in update_query

    assert update_params == (
        "provider-message-456",
        draft_id,
        clinic_id,
    )


def test_appointment_message_send_creates_thread_when_missing(
    monkeypatch,
):
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from uuid import uuid4

    import app.copilot.router as copilot_router
    from app.copilot.schemas import (
        AppointmentMessageSendRequest,
    )

    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()
    draft_id = uuid4()
    thread_id = uuid4()
    prepared_message_id = uuid4()

    patient_phone = "+213555000001"
    provider_instance = "clinic-test"

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

    # Ordre attendu dans la première transaction :
    #
    # 1. recherche du thread existant -> aucun
    # 2. validation du draft
    # 3. récupération du téléphone patient
    # 4. récupération de l'intégration Evolution active
    first_cursor = FakeCursor(
        fetchone_results=[
            None,
            {
                "id": draft_id,
            },
            {
                "phone": patient_phone,
            },
            {
                "provider_instance": provider_instance,
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

    message = (
        "Bonjour, confirmez-vous votre "
        "rendez-vous demain ?"
    )

    created_thread = {
        "id": thread_id,
        "patient_id": patient_id,
        "provider": "evolution",
        "provider_instance": provider_instance,
        "sender_phone": patient_phone,
    }

    prepared_thread = {
        "id": thread_id,
        "provider_instance": provider_instance,
        "sender_phone": patient_phone,
    }

    prepared_message = {
        "id": prepared_message_id,
        "body": message,
    }

    sent_message = {
        **prepared_message,
        "status": "sent",
        "external_id": "provider-message-456",
    }

    get_or_create_thread_mock = AsyncMock(
        return_value=created_thread
    )

    prepare_message_mock = AsyncMock(
        return_value=(
            prepared_thread,
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
        get_or_create_thread_mock,
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

    payload = AppointmentMessageSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        message_kind="pending_confirmation",
        message=message,
    )

    result = asyncio.run(
        copilot_router.send_appointment_message_draft_endpoint(
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
    assert result["message"] == sent_message

    get_or_create_thread_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        patient_id=patient_id,
        channel="whatsapp",
        sender_phone=patient_phone,
        provider="evolution",
        provider_instance=provider_instance,
        external_thread_id=None,
    )

    prepare_message_mock.assert_awaited_once_with(
        cur=first_cursor,
        clinic_id=clinic_id,
        thread_id=thread_id,
        user_id=user_id,
        body=message,
    )

    send_mock.assert_awaited_once_with(
        instance=provider_instance,
        sender_phone=patient_phone,
        text=message,
    )

    # Confirmation/no-show :
    # aucun workflow de réservation ne doit être armé.
    save_state_mock.assert_not_awaited()


def test_appointment_message_send_marks_task_completed(
    monkeypatch,
):
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    from uuid import uuid4

    import app.copilot.router as copilot_router
    from app.copilot.schemas import (
        AppointmentMessageSendRequest,
    )

    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()
    draft_id = uuid4()
    thread_id = uuid4()
    prepared_message_id = uuid4()

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

        def cursor(self):
            return self._cursor

        async def commit(self):
            pass

    first_cursor = FakeCursor(
        [
            {"id": thread_id},
            {"id": draft_id},
        ]
    )

    second_cursor = FakeCursor()

    connections = [
        FakeConnection(first_cursor),
        FakeConnection(second_cursor),
    ]

    @asynccontextmanager
    async def fake_connection():
        yield connections.pop(0)

    message = "Bonjour, confirmez-vous votre rendez-vous ?"

    prepare_message_mock = AsyncMock(
        return_value=(
            {
                "id": thread_id,
                "provider_instance": "clinic-test",
                "sender_phone": "+213555000001",
            },
            {
                "id": prepared_message_id,
                "body": message,
            },
        )
    )

    send_mock = AsyncMock(
        return_value={
            "external_id": "provider-message-789",
            "response": {"accepted": True},
        }
    )

    mark_sent_mock = AsyncMock(
        return_value={
            "id": prepared_message_id,
            "body": message,
            "status": "sent",
            "external_id": "provider-message-789",
        }
    )

    task_state_mock = AsyncMock()
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
        "record_copilot_audit_event",
        audit_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "publish_conversation_event",
        publish_mock,
    )
    monkeypatch.setattr(
        copilot_router,
        "upsert_task_state",
        task_state_mock,
    )

    payload = AppointmentMessageSendRequest(
        draft_id=draft_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        message_kind="pending_confirmation",
        message=message,
    )

    result = asyncio.run(
        copilot_router.send_appointment_message_draft_endpoint(
            payload=payload,
            current_clinic=clinic_id,
            user={
                "id": user_id,
                "full_name": "Utilisateur Test",
            },
        )
    )

    assert result["status"] == "sent"

    reminder_updates = [
        (query, params)
        for query, params in second_cursor.executed
        if "appointment_confirmation_reminders"
        in str(query)
    ]

    assert len(reminder_updates) == 1

    reminder_query, reminder_params = (
        reminder_updates[0]
    )

    assert (
        "INSERT INTO appointment_confirmation_reminders"
        in str(reminder_query)
    )
    assert (
        "ON CONFLICT (appointment_id)"
        in str(reminder_query)
    )
    assert "DO UPDATE SET" in str(reminder_query)
    assert "'sent'" in str(reminder_query)

    assert reminder_params == (
        clinic_id,
        "clinic-test",
        "provider-message-789",
        appointment_id,
        clinic_id,
        patient_id,
    )

    task_state_mock.assert_awaited_once_with(
        cur=second_cursor,
        clinic_id=clinic_id,
        task_key=f"confirmation:{appointment_id}",
        status="completed",
        snoozed_until=None,
        assigned_user_id=None,
    )
