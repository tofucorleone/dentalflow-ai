import asyncio
from unittest.mock import Mock
from uuid import UUID

from app import appointment_confirmation_service


CLINIC_ID = UUID(
    "576a0895-f0f1-4e4f-b78c-c1d81d2da562"
)


def test_non_positive_reply_returns_none_without_database_access(
    monkeypatch,
):
    connection_mock = Mock(
        side_effect=AssertionError(
            "La DB ne doit pas être ouverte "
            "pour une réponse non positive."
        )
    )

    monkeypatch.setattr(
        appointment_confirmation_service,
        "connection",
        connection_mock,
    )

    result = asyncio.run(
        appointment_confirmation_service
        .handle_appointment_confirmation_reply(
            clinic_id=CLINIC_ID,
            patient_phone="+213550755740",
            reply_text="NON",
        )
    )

    assert result is None
    connection_mock.assert_not_called()


class FakeCursorNoReminder:
    def __init__(self):
        self.executed_query = None
        self.executed_params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, params=None):
        self.executed_query = " ".join(query.split())
        self.executed_params = params

    async def fetchone(self):
        return None


class FakeConnectionNoReminder:
    def __init__(self):
        self.cursor_instance = FakeCursorNoReminder()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance


class FakeConnectionContextNoReminder:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_positive_reply_without_sent_reminder_returns_none(
    monkeypatch,
):
    fake_connection = FakeConnectionNoReminder()

    def fake_connection_factory():
        return FakeConnectionContextNoReminder(fake_connection)

    mark_confirmed_mock = Mock(
        side_effect=AssertionError(
            "mark_appointment_confirmed ne doit pas être appelé "
            "sans reminder sent correspondant."
        )
    )

    monkeypatch.setattr(
        appointment_confirmation_service,
        "connection",
        fake_connection_factory,
    )
    monkeypatch.setattr(
        appointment_confirmation_service,
        "mark_appointment_confirmed",
        mark_confirmed_mock,
    )

    result = asyncio.run(
        appointment_confirmation_service
        .handle_appointment_confirmation_reply(
            clinic_id=CLINIC_ID,
            patient_phone="  +213550755740  ",
            reply_text="OUI",
        )
    )

    assert result is None
    mark_confirmed_mock.assert_not_called()

    cursor = fake_connection.cursor_instance

    assert "r.status = 'sent'" in cursor.executed_query
    assert "a.status = 'pending'" in cursor.executed_query
    assert cursor.executed_params == (
        CLINIC_ID,
        "+213550755740",
    )


from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4


class FakeCursorPositiveConfirmation:
    def __init__(
        self,
        reminder: dict,
        confirmed_reminder: dict,
    ):
        self.reminder = reminder
        self.confirmed_reminder = confirmed_reminder
        self.execute_count = 0
        self.executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, params=None):
        self.execute_count += 1
        self.executed.append(
            (
                " ".join(query.split()),
                params,
            )
        )

    async def fetchone(self):
        if self.execute_count == 1:
            return self.reminder

        if self.execute_count == 2:
            return self.confirmed_reminder

        raise AssertionError(
            "fetchone() appelé à une étape inattendue : "
            f"{self.execute_count}"
        )


class FakeConnectionPositiveConfirmation:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.commit = AsyncMock()

    def cursor(self):
        return self.cursor_instance


def test_positive_reply_confirms_appointment_and_reminder(
    monkeypatch,
):
    appointment_id = uuid4()
    reminder_id = uuid4()
    patient_id = uuid4()

    reminder = {
        "id": reminder_id,
        "clinic_id": CLINIC_ID,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "patient_phone": "+213550755740",
        "status": "sent",
        "sent_at": None,
        "appointment_status": "pending",
    }

    confirmed_reminder = {
        **reminder,
        "status": "confirmed",
        "patient_reply": "OUI",
    }

    confirmed_appointment = {
        "id": appointment_id,
        "clinic_id": CLINIC_ID,
        "patient_id": patient_id,
        "status": "confirmed",
    }

    cursor = FakeCursorPositiveConfirmation(
        reminder=reminder,
        confirmed_reminder=confirmed_reminder,
    )

    connection = FakeConnectionPositiveConfirmation(cursor)

    @asynccontextmanager
    async def fake_connection():
        yield connection

    mark_confirmed_mock = AsyncMock(
        return_value=confirmed_appointment
    )

    monkeypatch.setattr(
        appointment_confirmation_service,
        "connection",
        fake_connection,
    )

    monkeypatch.setattr(
        appointment_confirmation_service,
        "mark_appointment_confirmed",
        mark_confirmed_mock,
    )

    result = asyncio.run(
        appointment_confirmation_service
        .handle_appointment_confirmation_reply(
            clinic_id=CLINIC_ID,
            patient_phone=" +213550755740 ",
            reply_text="  OUI  ",
        )
    )

    mark_confirmed_mock.assert_awaited_once_with(
        cur=cursor,
        conn=connection,
        clinic_id=CLINIC_ID,
        appointment_id=appointment_id,
    )

    assert cursor.execute_count == 2

    first_query, first_params = cursor.executed[0]
    second_query, second_params = cursor.executed[1]

    assert "r.status = 'sent'" in first_query
    assert "a.status = 'pending'" in first_query

    assert first_params == (
        CLINIC_ID,
        "+213550755740",
    )

    assert (
        "UPDATE appointment_confirmation_reminders"
        in second_query
    )
    assert "status = 'confirmed'" in second_query
    assert "confirmed_at = NOW()" in second_query

    assert second_params == (
        "OUI",
        reminder_id,
    )

    connection.commit.assert_awaited_once()

    assert result == {
        "appointment": confirmed_appointment,
        "reminder": confirmed_reminder,
        "result": "confirmed",
    }


def test_positive_reply_with_non_pending_appointment_returns_none(
    monkeypatch,
):
    fake_connection = FakeConnectionNoReminder()

    def fake_connection_factory():
        return FakeConnectionContextNoReminder(fake_connection)

    mark_confirmed_mock = Mock(
        side_effect=AssertionError(
            "mark_appointment_confirmed ne doit pas être appelé "
            "si aucun RDV pending éligible n'est trouvé."
        )
    )

    monkeypatch.setattr(
        appointment_confirmation_service,
        "connection",
        fake_connection_factory,
    )
    monkeypatch.setattr(
        appointment_confirmation_service,
        "mark_appointment_confirmed",
        mark_confirmed_mock,
    )

    result = asyncio.run(
        appointment_confirmation_service
        .handle_appointment_confirmation_reply(
            clinic_id=CLINIC_ID,
            patient_phone="+213550755740",
            reply_text="OUI",
        )
    )

    assert result is None
    mark_confirmed_mock.assert_not_called()

    cursor = fake_connection.cursor_instance

    assert "a.status = 'pending'" in cursor.executed_query
    assert cursor.executed_params == (
        CLINIC_ID,
        "+213550755740",
    )
