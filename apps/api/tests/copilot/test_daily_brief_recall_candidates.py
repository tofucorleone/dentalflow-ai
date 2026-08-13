import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

from app.copilot import service


class FakeCursor:
    pass


def without_draft_messages(
    candidates: list[dict],
) -> list[dict]:
    return [
        {
            key: value
            for key, value in candidate.items()
            if key != "draft_message"
        }
        for candidate in candidates
    ]


def test_daily_brief_enriches_released_slots_with_recall_candidates(
    monkeypatch,
):
    clinic_id = uuid4()
    user_id = uuid4()
    cancelled_patient_id = uuid4()
    candidate_patient_id = uuid4()
    practitioner_id = uuid4()
    appointment_id = uuid4()

    now = datetime(
        2026,
        8,
        4,
        8,
        0,
        tzinfo=timezone.utc,
    )

    cancelled_appointment = {
        "id": appointment_id,
        "clinic_id": clinic_id,
        "patient_id": cancelled_patient_id,
        "practitioner_id": practitioner_id,
        "treatment_id": None,
        "channel": "whatsapp",
        "status": "cancelled",
        "start_at": datetime(
            2026,
            8,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            9,
            30,
            tzinfo=timezone.utc,
        ),
        "google_calendar_event_id": None,
        "notes": None,
        "created_at": now,
        "updated_at": now,
        "patient_name": "Patient annulé",
        "patient_phone": "+213555000001",
        "practitioner_name": "Dr Martin",
        "treatment_name": None,
    }

    patient_rows = [
        {
            "patient_id": candidate_patient_id,
            "patient_name": "Patient candidat",
            "active": True,
            "preferred_practitioner_id": None,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
            },
            "last_goal": "Cherche un rendez-vous rapidement.",
            "has_active_overlap": False,
        }
    ]

    captured_query = {}

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
        return [cancelled_appointment]

    async def fake_list_recall_candidate_patients(
        *,
        cur,
        clinic_id,
        cancelled_patient_id,
        slot_start,
        slot_end,
        limit,
    ):
        captured_query.update(
            {
                "clinic_id": clinic_id,
                "cancelled_patient_id": cancelled_patient_id,
                "slot_start": slot_start,
                "slot_end": slot_end,
                "limit": limit,
            }
        )
        return patient_rows

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
                "full_name": "Utilisateur Test",
                "role": "owner",
            },
            now=now,
        )
    )

    assert len(result["released_slots"]) == 1

    released_slot = result["released_slots"][0]

    assert released_slot["appointment_id"] == appointment_id
    assert released_slot["cancelled_patient_id"] == cancelled_patient_id
    assert without_draft_messages(
        released_slot["recall_candidates"]
    ) == [
        {
            "patient_id": candidate_patient_id,
            "patient_name": "Patient candidat",
            "score": 90,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
                "Jour préféré correspondant",
                "Objectif récent lié à un rendez-vous",
            ],
            "requires_validation": True,
        }
    ]

    assert captured_query == {
        "clinic_id": clinic_id,
        "cancelled_patient_id": cancelled_patient_id,
        "slot_start": cancelled_appointment["start_at"],
        "slot_end": cancelled_appointment["end_at"],
        "limit": 100,
    }
