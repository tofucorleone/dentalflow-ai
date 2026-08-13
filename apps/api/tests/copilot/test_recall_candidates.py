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


def test_build_recall_candidates_scores_and_filters():
    practitioner_id = uuid4()
    cancelled_patient_id = uuid4()
    matching_patient_id = uuid4()
    partial_patient_id = uuid4()
    conflicting_patient_id = uuid4()

    slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": cancelled_patient_id,
        "practitioner_id": practitioner_id,
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

    candidates = [
        {
            "patient_id": cancelled_patient_id,
            "patient_name": "Patient annulé",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
            },
            "last_goal": None,
            "has_active_overlap": False,
        },
        {
            "patient_id": matching_patient_id,
            "patient_name": "Patient correspondant",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
            },
            "last_goal": "Cherche un rendez-vous rapidement.",
            "has_active_overlap": False,
        },
        {
            "patient_id": partial_patient_id,
            "patient_name": "Patient partiel",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
            },
            "last_goal": None,
            "has_active_overlap": False,
        },
        {
            "patient_id": conflicting_patient_id,
            "patient_name": "Patient en conflit",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
            },
            "last_goal": "Cherche un rendez-vous.",
            "has_active_overlap": True,
        },
        {
            "patient_id": uuid4(),
            "patient_name": "Patient inactif",
            "active": False,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
            },
            "last_goal": None,
            "has_active_overlap": False,
        },
    ]

    result = build_recall_candidates(
        released_slot=slot,
        patients=candidates,
        limit=5,
    )

    assert without_draft_messages(result) == [
        {
            "patient_id": matching_patient_id,
            "patient_name": "Patient correspondant",
            "score": 90,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
                "Jour préféré correspondant",
                "Objectif récent lié à un rendez-vous",
            ],
            "requires_validation": True,
        },
        {
            "patient_id": partial_patient_id,
            "patient_name": "Patient partiel",
            "score": 50,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
            ],
            "requires_validation": True,
        },
    ]


def test_build_recall_candidates_respects_limit():
    practitioner_id = uuid4()

    slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": uuid4(),
        "practitioner_id": practitioner_id,
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
            "patient_id": uuid4(),
            "patient_name": f"Patient {index}",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
            },
            "last_goal": None,
            "has_active_overlap": False,
        }
        for index in range(5)
    ]

    result = build_recall_candidates(
        released_slot=slot,
        patients=patients,
        limit=2,
    )

    assert len(result) == 2
