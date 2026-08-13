from datetime import datetime, timezone
from uuid import uuid4

from app.copilot.service import build_recall_candidates


def test_recall_candidate_draft_uses_clinic_timezone():
    patient_id = uuid4()

    released_slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": uuid4(),
        "practitioner_id": None,
        "practitioner_name": None,
        "start_at": datetime(
            2026,
            8,
            4,
            14,
            0,
            tzinfo=timezone.utc,
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            14,
            30,
            tzinfo=timezone.utc,
        ),
    }

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=[
            {
                "patient_id": patient_id,
                "patient_name": "Patient Test",
                "active": True,
                "preferences": {
                    "preferred_day": "mardi",
                },
                "last_goal": "Cherche un rendez-vous rapidement.",
                "has_active_overlap": False,
                "has_active_future_appointment": False,
            }
        ],
        timezone_name="Africa/Algiers",
        limit=5,
    )

    assert "mardi 4 août à 15:00" in result[0]["draft_message"]
