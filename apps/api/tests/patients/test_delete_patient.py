import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, call
from uuid import uuid4


class FakeCursor:
    def __init__(
        self,
        patient: dict,
        appointments: list[dict],
        deleted_patient: dict,
    ):
        self.patient = patient
        self.appointments = appointments
        self.deleted_patient = deleted_patient
        self.rowcount = -1
        self.execute_count = 0

    async def execute(self, query, params=None):
        self.execute_count += 1
        normalized_query = " ".join(query.split())

        if normalized_query.startswith(
            "DELETE FROM appointments"
        ):
            self.rowcount = len(self.appointments)

    async def fetchone(self):
        if self.execute_count == 1:
            return self.patient

        if self.execute_count == 4:
            return self.deleted_patient

        raise AssertionError(
            "fetchone() appelé à une étape inattendue : "
            f"{self.execute_count}"
        )

    async def fetchall(self):
        if self.execute_count != 2:
            raise AssertionError(
                "fetchall() appelé à une étape inattendue : "
                f"{self.execute_count}"
            )

        return self.appointments


class FakeCursorContext:
    def __init__(self, cursor: FakeCursor):
        self.cursor_instance = cursor

    async def __aenter__(self):
        return self.cursor_instance

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.cursor_instance = cursor
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def cursor(self):
        return FakeCursorContext(self.cursor_instance)


def test_delete_patient_removes_google_events_and_local_data(
    monkeypatch,
):
    from app import core

    clinic_id = uuid4()
    patient_id = uuid4()

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
        "phone": "+213555000001",
    }

    appointments = [
        {
            "id": uuid4(),
            "status": "confirmed",
            "google_calendar_event_id": "google-event-1",
            "calendar_id": "calendar-1@example.com",
        },
        {
            "id": uuid4(),
            "status": "pending",
            "google_calendar_event_id": "google-event-2",
            "calendar_id": "calendar-2@example.com",
        },
        {
            "id": uuid4(),
            "status": "cancelled",
            "google_calendar_event_id": "google-event-cancelled",
            "calendar_id": "calendar-3@example.com",
        },
    ]

    cursor = FakeCursor(
        patient=patient,
        appointments=appointments,
        deleted_patient=patient,
    )
    connection = FakeConnection(cursor)

    @asynccontextmanager
    async def fake_connection():
        yield connection

    delete_event_mock = AsyncMock()

    monkeypatch.setattr(
        core,
        "connection",
        fake_connection,
    )
    monkeypatch.setattr(
        core,
        "delete_event",
        delete_event_mock,
    )

    result = asyncio.run(
        core.delete_patient(
            patient_id=patient_id,
            current_clinic=clinic_id,
        )
    )

    assert result == {
        "id": patient_id,
        "full_name": "Patient Test",
        "phone": "+213555000001",
        "deleted_appointments": 3,
        "deleted_google_events": 2,
        "status": "deleted",
    }

    assert delete_event_mock.await_args_list == [
        call(
            "calendar-1@example.com",
            "google-event-1",
        ),
        call(
            "calendar-2@example.com",
            "google-event-2",
        ),
    ]

    connection.commit.assert_awaited_once()
    connection.rollback.assert_not_awaited()


def test_delete_patient_rolls_back_when_google_calendar_fails(
    monkeypatch,
):
    from fastapi import HTTPException

    from app import core
    from app.google_calendar import CalendarOperationError

    clinic_id = uuid4()
    patient_id = uuid4()

    patient = {
        "id": patient_id,
        "full_name": "Patient Test",
        "phone": "+213555000002",
    }

    appointments = [
        {
            "id": uuid4(),
            "status": "confirmed",
            "google_calendar_event_id": "google-event-error",
            "calendar_id": "calendar@example.com",
        },
    ]

    cursor = FakeCursor(
        patient=patient,
        appointments=appointments,
        deleted_patient=patient,
    )
    connection = FakeConnection(cursor)

    @asynccontextmanager
    async def fake_connection():
        yield connection

    delete_event_mock = AsyncMock(
        side_effect=CalendarOperationError(
            "Suppression Google impossible.",
        )
    )

    monkeypatch.setattr(
        core,
        "connection",
        fake_connection,
    )
    monkeypatch.setattr(
        core,
        "delete_event",
        delete_event_mock,
    )

    try:
        asyncio.run(
            core.delete_patient(
                patient_id=patient_id,
                current_clinic=clinic_id,
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 502
        assert "Aucune donnée locale supprimée" in exc.detail
    else:
        raise AssertionError(
            "Une HTTPException 502 était attendue."
        )

    delete_event_mock.assert_awaited_once_with(
        "calendar@example.com",
        "google-event-error",
    )

    connection.rollback.assert_awaited_once()
    connection.commit.assert_not_awaited()

    assert cursor.execute_count == 2
