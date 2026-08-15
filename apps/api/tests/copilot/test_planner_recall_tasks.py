from uuid import uuid4

from app.copilot.planner import build_recommended_actions


def test_build_recommended_actions_enriches_recall_task():
    patient_id = uuid4()

    actions = build_recommended_actions(
        priorities={},
        released_slots=[],
        overdue_recall_patients=[
            {
                "patient_id": patient_id,
                "patient_name": "Ahmed Benali",
                "phone": "+213555000000",
                "priority": "high",
                "score": 85,
                "reasons": [
                    "Dernière visite il y a plus de 24 mois",
                    "Téléphone disponible",
                    "Aucun rendez-vous futur",
                ],
                "draft_message": (
                    "Bonjour Ahmed Benali, "
                    "le cabinet vous propose un contrôle de suivi. "
                    "Souhaitez-vous prendre rendez-vous ?"
                ),
            }
        ],
    )

    assert len(actions) == 1

    task = actions[0]

    assert task["id"] == f"recall:{patient_id}"
    assert task["type"] == "recall"
    assert task["patient_id"] == patient_id
    assert task["appointment_id"] is None

    assert task["draft_message"] == (
        "Bonjour Ahmed Benali, "
        "le cabinet vous propose un contrôle de suivi. "
        "Souhaitez-vous prendre rendez-vous ?"
    )

    assert task["reasons"] == [
        "Dernière visite il y a plus de 24 mois",
        "Téléphone disponible",
        "Aucun rendez-vous futur",
    ]

    assert task["recommended_action"] == (
        "Préparer un message de rappel pour Ahmed Benali "
        "avant tout envoi."
    )

    assert task["requires_validation"] is True


def test_recall_recommendation_fields_reach_copilot_task():
    from app.copilot.tasks import (
        build_task_from_recommendation,
    )

    patient_id = uuid4()

    recommendation = {
        "id": f"recall:{patient_id}",
        "type": "recall",
        "priority": "high",
        "score": 85,
        "title": "Recontacter Ahmed Benali",
        "description": (
            "Dernière visite il y a plus de 24 mois"
        ),
        "recommended_action": (
            "Préparer un message de rappel pour "
            "Ahmed Benali avant tout envoi."
        ),
        "patient_id": patient_id,
        "appointment_id": None,
        "draft_message": (
            "Bonjour Ahmed Benali, "
            "le cabinet vous propose un contrôle de suivi. "
            "Souhaitez-vous prendre rendez-vous ?"
        ),
        "reasons": [
            "Dernière visite il y a plus de 24 mois",
            "Téléphone disponible",
            "Aucun rendez-vous futur",
        ],
        "actions": [
            {
                "type": "navigate",
                "label": "Ouvrir la fiche de Ahmed Benali",
                "href": f"/patients/{patient_id}",
            }
        ],
        "requires_validation": True,
    }

    task = build_task_from_recommendation(
        recommendation
    )

    assert task["patient_id"] == patient_id

    assert task["recommended_action"] == (
        "Préparer un message de rappel pour "
        "Ahmed Benali avant tout envoi."
    )

    assert task["draft_message"] == (
        "Bonjour Ahmed Benali, "
        "le cabinet vous propose un contrôle de suivi. "
        "Souhaitez-vous prendre rendez-vous ?"
    )

    assert task["reasons"] == [
        "Dernière visite il y a plus de 24 mois",
        "Téléphone disponible",
        "Aucun rendez-vous futur",
    ]

    assert task["requires_validation"] is True
