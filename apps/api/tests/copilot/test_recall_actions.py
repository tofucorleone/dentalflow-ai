from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.copilot.service import build_recall_actions


def test_build_recall_actions_from_primary_candidate():
    appointment_id = uuid4()
    patient_id = uuid4()

    released_slots = [
        {
            "appointment_id": appointment_id,
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
            "recall_candidates": [
                {
                    "patient_id": patient_id,
                    "patient_name": "Patient principal",
                    "score": 95,
                    "match_level": "primary",
                    "reasons": [
                        "Praticien préféré correspondant",
                        "Jour préféré correspondant",
                        "Horaire préféré correspondant",
                    ],
                    "requires_validation": True,
                }
            ],
        }
    ]

    result = build_recall_actions(
        released_slots=released_slots,
        timezone_name="Africa/Algiers",
    )

    assert result == [
        {
            "id": f"propose_recall:{appointment_id}",
            "priority": "high",
            "score": 95,
            "title": "1 patient prioritaire peut être rappelé",
            "description": (
                "Un candidat fortement compatible a été identifié "
                "pour le créneau libéré du 4 août 2026 à 09:00."
            ),
            "recommended_action": (
                "Vérifier le dossier de Patient principal et préparer "
                "une proposition de rendez-vous avec Dr Martin."
            ),
            "requires_validation": True,
        }
    ]


def test_build_recall_actions_from_secondary_candidates():
    appointment_id = uuid4()

    released_slots = [
        {
            "appointment_id": appointment_id,
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
            "recall_candidates": [
                {
                    "patient_id": uuid4(),
                    "patient_name": "Patient secondaire 1",
                    "score": 55,
                    "match_level": "secondary",
                    "reasons": [
                        "Jour préféré correspondant",
                        "Objectif récent lié à un rendez-vous",
                        "Aucun rendez-vous actif futur",
                    ],
                    "requires_validation": True,
                },
                {
                    "patient_id": uuid4(),
                    "patient_name": "Patient secondaire 2",
                    "score": 30,
                    "match_level": "secondary",
                    "reasons": [
                        "Objectif récent lié à un rendez-vous",
                        "Aucun rendez-vous actif futur",
                    ],
                    "requires_validation": True,
                },
            ],
        }
    ]

    result = build_recall_actions(
        released_slots=released_slots,
        timezone_name="Africa/Algiers",
    )

    assert result == [
        {
            "id": f"propose_recall:{appointment_id}",
            "priority": "medium",
            "score": 65,
            "title": "2 patients peuvent être rappelés",
            "description": (
                "Des candidats secondaires ont été identifiés "
                "pour le créneau libéré du 4 août 2026 à 14:00."
            ),
            "recommended_action": (
                "Examiner les candidats et choisir le patient "
                "à contacter avant de préparer une proposition."
            ),
            "requires_validation": True,
        }
    ]


def test_build_recall_actions_ignores_slots_without_candidates():
    result = build_recall_actions(
        released_slots=[
            {
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
                "recall_candidates": [],
            }
        ],
        timezone_name="Africa/Algiers",
    )

    assert result == []
