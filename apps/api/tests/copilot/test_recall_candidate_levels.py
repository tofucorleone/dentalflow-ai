from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.copilot.service import build_recall_candidates


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


def test_recall_candidates_returns_primary_and_secondary_levels():
    primary_patient_id = uuid4()
    secondary_patient_id = uuid4()

    released_slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": uuid4(),
        "practitioner_id": uuid4(),
        "practitioner_name": "Dr Martin",
        "start_at": datetime(
            2026,
            8,
            4,
            9,
            0,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            9,
            30,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
    }

    patients = [
        {
            "patient_id": primary_patient_id,
            "patient_name": "Patient principal",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
            },
            "last_goal": None,
            "has_active_overlap": False,
            "has_active_future_appointment": False,
        },
        {
            "patient_id": secondary_patient_id,
            "patient_name": "Patient secondaire",
            "active": True,
            "preferences": {},
            "last_goal": "Cherche un rendez-vous rapidement.",
            "has_active_overlap": False,
            "has_active_future_appointment": False,
        },
        {
            "patient_id": uuid4(),
            "patient_name": "Patient déjà planifié",
            "active": True,
            "preferences": {},
            "last_goal": "Cherche un rendez-vous.",
            "has_active_overlap": False,
            "has_active_future_appointment": True,
        },
        {
            "patient_id": uuid4(),
            "patient_name": "Patient sans signal",
            "active": True,
            "preferences": {},
            "last_goal": None,
            "has_active_overlap": False,
            "has_active_future_appointment": False,
        },
    ]

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=patients,
        limit=5,
    )

    assert without_draft_messages(result) == [
        {
            "patient_id": primary_patient_id,
            "patient_name": "Patient principal",
            "score": 50,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
            ],
            "requires_validation": True,
        },
        {
            "patient_id": secondary_patient_id,
            "patient_name": "Patient secondaire",
            "score": 30,
            "match_level": "secondary",
            "reasons": [
                "Objectif récent lié à un rendez-vous",
                "Aucun rendez-vous actif futur",
            ],
            "requires_validation": True,
        },
    ]


def test_secondary_candidate_is_not_created_from_single_weak_signal():
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
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
        "end_at": datetime(
            2026,
            8,
            4,
            14,
            30,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
    }

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=[
            {
                "patient_id": uuid4(),
                "patient_name": "Signal faible",
                "active": True,
                "preferences": {},
                "last_goal": "Cherche un rendez-vous.",
                "has_active_overlap": False,
                "has_active_future_appointment": True,
            }
        ],
        limit=5,
    )

    assert without_draft_messages(result) == []
