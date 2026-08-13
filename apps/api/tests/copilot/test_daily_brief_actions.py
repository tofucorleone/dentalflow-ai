from app.copilot.service import build_actions


def test_build_actions_from_priorities():
    actions = build_actions(
        priorities={
            "pending_confirmation": 3,
            "cancelled_today": 2,
            "no_show": 1,
            "late_active": 1,
        }
    )

    assert actions == [
        {
            "id": "review_no_show",
            "priority": "high",
            "score": 100,
            "title": "1 patient absent aujourd’hui",
            "description": (
                "Un rendez-vous est marqué comme non honoré."
            ),
            "recommended_action": (
                "Vérifier le dossier et préparer une relance."
            ),
            "requires_validation": False,
        },
        {
            "id": "review_late_active",
            "priority": "high",
            "score": 95,
            "title": "1 rendez-vous actif est dépassé",
            "description": (
                "Un rendez-vous encore actif a une heure de début passée."
            ),
            "recommended_action": (
                "Vérifier son statut avant toute autre action."
            ),
            "requires_validation": False,
        },
        {
            "id": "review_cancelled",
            "priority": "high",
            "score": 70,
            "title": "2 rendez-vous annulés aujourd’hui",
            "description": (
                "Ces annulations ont potentiellement libéré des créneaux."
            ),
            "recommended_action": (
                "Examiner les créneaux et la liste des patients à rappeler."
            ),
            "requires_validation": False,
        },
        {
            "id": "pending_confirmation",
            "priority": "medium",
            "score": 70,
            "title": "3 confirmations en attente",
            "description": (
                "Des rendez-vous du jour sont encore au statut pending."
            ),
            "recommended_action": (
                "Préparer les confirmations patient."
            ),
            "requires_validation": False,
        },
    ]


def test_build_actions_returns_empty_list_without_priorities():
    actions = build_actions(
        priorities={
            "pending_confirmation": 0,
            "cancelled_today": 0,
            "no_show": 0,
            "late_active": 0,
        }
    )

    assert actions == []
