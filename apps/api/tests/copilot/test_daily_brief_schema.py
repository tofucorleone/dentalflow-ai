from datetime import datetime, timezone
from uuid import uuid4

from app.copilot.schemas import DailyBriefResponse


def test_daily_brief_schema_hides_internal_fields():
    clinic_id = uuid4()
    user_id = uuid4()
    patient_id = uuid4()
    appointment_id = uuid4()

    payload = {
        "date": "2026-08-04",
        "timezone": "Africa/Algiers",
        "clinic_id": clinic_id,
        "user": {
            "id": user_id,
            "full_name": "ToFu Corleone",
            "role": "owner",
        },
        "summary": {
            "total": 1,
            "pending": 0,
            "confirmed": 1,
            "cancelled": 0,
            "completed": 0,
            "no_show": 0,
            "active": 1,
            "upcoming": 1,
        },
        "priorities": {
            "pending_confirmation": 0,
            "cancelled_today": 0,
            "no_show": 0,
            "late_active": 0,
        },
        "actions": [],
        "appointments": [
            {
                "id": appointment_id,
                "clinic_id": clinic_id,
                "patient_id": patient_id,
                "patient_phone": "+213555000001",
                "practitioner_id": None,
                "treatment_id": None,
                "patient_name": "Patient Test",
                "practitioner_name": None,
                "treatment_name": None,
                "channel": "dashboard",
                "status": "confirmed",
                "start_at": datetime(
                    2026,
                    8,
                    4,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                "end_at": datetime(
                    2026,
                    8,
                    4,
                    10,
                    30,
                    tzinfo=timezone.utc,
                ),
                "google_calendar_event_id": "secret-google-id",
                "notes": "Note administrative.",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ],
    }

    result = DailyBriefResponse.model_validate(payload)
    serialized = result.model_dump(mode="json")

    appointment = serialized["appointments"][0]

    assert "clinic_id" not in appointment
    assert "patient_phone" not in appointment
    assert "google_calendar_event_id" not in appointment
    assert "created_at" not in appointment
    assert "updated_at" not in appointment

    assert appointment["patient_name"] == "Patient Test"
    assert appointment["status"] == "confirmed"
