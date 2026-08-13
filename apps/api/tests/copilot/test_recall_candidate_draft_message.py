from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.copilot.service import build_recall_candidates


def test_recall_candidate_contains_draft_message():
    patient_id = uuid4()

    released_slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": uuid4(),
        "practitioner_id": uuid4(),
        "practitioner_name": "Dr Martin",
        "start_at": datetime(
            2026,
            8,
            4,
            15,
            0,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            15,
            30,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
    }

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=[
            {
                "patient_id": patient_id,
                "patient_name": "Farid",
                "active": True,
                "preferences": {
                    "preferred_practitioner": "Dr Martin",
                    "preferred_day": "mardi",
                },
                "last_goal": "Cherche un rendez-vous rapidement.",
                "has_active_overlap": False,
                "has_active_future_appointment": False,
            }
        ],
        limit=5,
    )

    assert result == [
        {
            "patient_id": patient_id,
            "patient_name": "Farid",
            "score": 90,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
                "Jour préféré correspondant",
                "Objectif récent lié à un rendez-vous",
            ],
            "requires_validation": True,
            "draft_message": (
                "Bonjour Farid,\n\n"
                "Un créneau vient de se libérer avec Dr Martin "
                "le mardi 4 août à 15:00.\n\n"
                "Souhaitez-vous en profiter ?\n\n"
                "Répondez simplement OUI pour que nous puissions "
                "vous le réserver."
            ),
        }
    ]


def test_recall_candidate_draft_message_handles_missing_name():
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
            15,
            0,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            15,
            30,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
    }

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=[
            {
                "patient_id": patient_id,
                "patient_name": None,
                "active": True,
                "preferences": {
                    "preferred_day": "mardi",
                },
                "last_goal": "Cherche un rendez-vous rapidement.",
                "has_active_overlap": False,
                "has_active_future_appointment": False,
            }
        ],
        limit=5,
    )

    assert result[0]["draft_message"] == (
        "Bonjour,\n\n"
        "Un créneau vient de se libérer "
        "le mardi 4 août à 15:00.\n\n"
        "Souhaitez-vous en profiter ?\n\n"
        "Répondez simplement OUI pour que nous puissions "
        "vous le réserver."
    )
