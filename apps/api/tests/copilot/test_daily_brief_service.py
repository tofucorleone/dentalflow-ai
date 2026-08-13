import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from app.copilot import service


class FakeCursor:
    pass


def test_build_daily_brief_counts_statuses_and_upcoming(monkeypatch):
    clinic_id = uuid4()
    user_id = uuid4()
    practitioner_id = uuid4()
    patient_id = uuid4()

    now = datetime(
        2026,
        8,
        4,
        10,
        0,
        tzinfo=timezone.utc,
    )

    appointments = [
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "treatment_id": None,
            "channel": "dashboard",
            "status": "confirmed",
            "start_at": now + timedelta(hours=1),
            "end_at": now + timedelta(hours=1, minutes=30),
            "google_calendar_event_id": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "patient_name": "Patient Confirmé",
            "patient_phone": "+213555000001",
            "practitioner_name": "Dr Sara",
            "treatment_name": None,
        },
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "treatment_id": None,
            "channel": "whatsapp",
            "status": "pending",
            "start_at": now - timedelta(hours=1),
            "end_at": now - timedelta(minutes=30),
            "google_calendar_event_id": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "patient_name": "Patient En attente",
            "patient_phone": "+213555000002",
            "practitioner_name": "Dr Sara",
            "treatment_name": None,
        },
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "treatment_id": None,
            "channel": "phone",
            "status": "cancelled",
            "start_at": now + timedelta(hours=2),
            "end_at": now + timedelta(hours=2, minutes=30),
            "google_calendar_event_id": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "patient_name": "Patient Annulé",
            "patient_phone": "+213555000003",
            "practitioner_name": "Dr Sara",
            "treatment_name": None,
        },
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "treatment_id": None,
            "channel": "dashboard",
            "status": "completed",
            "start_at": now - timedelta(hours=3),
            "end_at": now - timedelta(hours=2, minutes=30),
            "google_calendar_event_id": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "patient_name": "Patient Terminé",
            "patient_phone": "+213555000004",
            "practitioner_name": "Dr Sara",
            "treatment_name": None,
        },
        {
            "id": uuid4(),
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "practitioner_id": practitioner_id,
            "treatment_id": None,
            "channel": "dashboard",
            "status": "no_show",
            "start_at": now - timedelta(hours=2),
            "end_at": now - timedelta(hours=1, minutes=30),
            "google_calendar_event_id": None,
            "notes": None,
            "created_at": now,
            "updated_at": now,
            "patient_name": "Patient Absent",
            "patient_phone": "+213555000005",
            "practitioner_name": "Dr Sara",
            "treatment_name": None,
        },
    ]

    captured_period = {}

    async def fake_clinic_timezone(cur, requested_clinic_id):
        assert requested_clinic_id == clinic_id
        return "Africa/Algiers"

    async def fake_list_appointments_for_period(
        *,
        cur,
        clinic_id,
        date_from,
        date_to,
        limit,
    ):
        captured_period.update(
            {
                "clinic_id": clinic_id,
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit,
            }
        )
        return appointments


    async def fake_list_recall_candidate_patients(
        *,
        cur,
        clinic_id,
        cancelled_patient_id,
        slot_start,
        slot_end,
        limit,
    ):
        return []

    monkeypatch.setattr(
        service,
        "clinic_timezone",
        fake_clinic_timezone,
    )
    monkeypatch.setattr(
        service,
        "list_appointments_for_period",
        fake_list_appointments_for_period,
    )
    monkeypatch.setattr(
        service,
        "list_recall_candidate_patients",
        fake_list_recall_candidate_patients,
    )
    monkeypatch.setattr(
        service,
        "list_overdue_recall_patients",
        AsyncMock(return_value=[]),
    )

    result = asyncio.run(
        service.build_daily_brief(
            cur=FakeCursor(),
            clinic_id=clinic_id,
            user={
                "id": user_id,
                "full_name": "Secrétaire Test",
                "role": "staff",
            },
            now=now,
        )
    )

    assert result["date"] == "2026-08-04"
    assert result["timezone"] == "Africa/Algiers"
    assert result["clinic_id"] == str(clinic_id)
    assert result["user"] == {
        "id": str(user_id),
        "full_name": "Secrétaire Test",
        "role": "staff",
    }

    assert result["summary"] == {
        "total": 5,
        "pending": 1,
        "confirmed": 1,
        "cancelled": 1,
        "completed": 1,
        "no_show": 1,
        "active": 2,
        "upcoming": 1,
    }

    assert result["appointments"] == appointments

    assert captured_period["clinic_id"] == clinic_id
    assert captured_period["limit"] == 500
    assert captured_period["date_from"].tzinfo is not None
    assert captured_period["date_to"].tzinfo is not None
    assert (
        captured_period["date_to"]
        - captured_period["date_from"]
    ) == timedelta(days=1)
