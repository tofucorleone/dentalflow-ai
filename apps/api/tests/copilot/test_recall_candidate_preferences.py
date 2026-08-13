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


def test_recall_candidates_excludes_incompatible_preferences():
    practitioner_id = uuid4()

    released_slot = {
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

    compatible_patient_id = uuid4()
    no_time_preference_patient_id = uuid4()
    secondary_patient_id = uuid4()

    patients = [
        {
            "patient_id": uuid4(),
            "patient_name": "Jour incompatible",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "vendredi",
            },
            "last_goal": "Cherche un rendez-vous.",
            "has_active_overlap": False,
        },
        {
            "patient_id": uuid4(),
            "patient_name": "Horaire incompatible",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
                "preferred_time": "après 17h",
            },
            "last_goal": "Cherche un rendez-vous.",
            "has_active_overlap": False,
        },
        {
            "patient_id": compatible_patient_id,
            "patient_name": "Patient compatible",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
                "preferred_day": "mardi",
                "preferred_time": "matin",
            },
            "last_goal": "Cherche un rendez-vous rapidement.",
            "has_active_overlap": False,
        },
        {
            "patient_id": no_time_preference_patient_id,
            "patient_name": "Patient praticien uniquement",
            "active": True,
            "preferences": {
                "preferred_practitioner": "Dr Martin",
            },
            "last_goal": None,
            "has_active_overlap": False,
        },
        {
            "patient_id": secondary_patient_id,
            "patient_name": "Objectif uniquement",
            "active": True,
            "preferences": {},
            "last_goal": "Cherche un rendez-vous rapidement.",
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
            "patient_id": compatible_patient_id,
            "patient_name": "Patient compatible",
            "score": 110,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
                "Jour préféré correspondant",
                "Horaire préféré correspondant",
                "Objectif récent lié à un rendez-vous",
            ],
            "requires_validation": True,
        },
        {
            "patient_id": no_time_preference_patient_id,
            "patient_name": "Patient praticien uniquement",
            "score": 50,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
            ],
            "requires_validation": True,
        },
        {
            "patient_id": secondary_patient_id,
            "patient_name": "Objectif uniquement",
            "score": 30,
            "match_level": "secondary",
            "reasons": [
                "Objectif récent lié à un rendez-vous",
                "Aucun rendez-vous actif futur",
            ],
            "requires_validation": True,
        },
    ]


def test_recall_candidates_accepts_after_hour_preference():
    patient_id = uuid4()

    released_slot = {
        "appointment_id": uuid4(),
        "cancelled_patient_id": uuid4(),
        "practitioner_id": uuid4(),
        "practitioner_name": "Dr Martin",
        "start_at": datetime(
            2026,
            8,
            7,
            17,
            30,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
        "end_at": datetime(
            2026,
            8,
            7,
            18,
            0,
            tzinfo=ZoneInfo("Africa/Algiers"),
        ),
    }

    result = build_recall_candidates(
        released_slot=released_slot,
        patients=[
            {
                "patient_id": patient_id,
                "patient_name": "Patient après 17h",
                "active": True,
                "preferences": {
                    "preferred_practitioner": "Dr Martin",
                    "preferred_day": "vendredi",
                    "preferred_time": "après 17h",
                },
                "last_goal": None,
                "has_active_overlap": False,
            }
        ],
        limit=5,
    )

    assert without_draft_messages(result) == [
        {
            "patient_id": patient_id,
            "patient_name": "Patient après 17h",
            "score": 95,
            "match_level": "primary",
            "reasons": [
                "Praticien préféré correspondant",
                "Jour préféré correspondant",
                "Horaire préféré correspondant",
            ],
            "requires_validation": True,
        }
    ]
