import asyncio
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.copilot.planner import (
    build_appointment_message_actions,
)
from app.copilot.tasks import (
    hydrate_prepared_appointment_message_drafts,
)


TZ = ZoneInfo("Africa/Algiers")


def test_builds_confirmation_task_for_tomorrow_appointment():
    appointment_id = uuid4()
    patient_id = uuid4()

    now = datetime(
        2026, 8, 16, 10, 0,
        tzinfo=TZ,
    )

    appointments = [
        {
            "id": appointment_id,
            "patient_id": patient_id,
            "patient_name": "Patient Test WhatsApp",
            "status": "pending",
            "start_at": datetime(
                2026, 8, 17, 14, 30,
                tzinfo=TZ,
            ),
        }
    ]

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=now,
    )

    assert len(actions) == 1

    task = actions[0]

    assert task["id"] == f"confirmation:{appointment_id}"
    assert task["type"] == "pending_confirmation"
    assert task["appointment_id"] == appointment_id
    assert task["patient_id"] == patient_id
    assert task["requires_validation"] is True
    assert "Patient Test WhatsApp" in task["title"]
    assert task["draft_message"]


def test_does_not_build_confirmation_before_j_minus_1():
    appointment_id = uuid4()

    now = datetime(
        2026, 8, 16, 10, 0,
        tzinfo=TZ,
    )

    appointments = [
        {
            "id": appointment_id,
            "patient_id": uuid4(),
            "patient_name": "Patient Test",
            "status": "pending",
            "start_at": datetime(
                2026, 8, 18, 14, 30,
                tzinfo=TZ,
            ),
        }
    ]

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=now,
    )

    assert actions == []


def test_builds_no_show_message_task():
    appointment_id = uuid4()
    patient_id = uuid4()

    now = datetime(
        2026, 8, 16, 16, 0,
        tzinfo=TZ,
    )

    appointments = [
        {
            "id": appointment_id,
            "patient_id": patient_id,
            "patient_name": "Patient Test WhatsApp",
            "status": "no_show",
            "start_at": datetime(
                2026, 8, 16, 14, 30,
                tzinfo=TZ,
            ),
        }
    ]

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=now,
    )

    assert len(actions) == 1

    task = actions[0]

    assert task["id"] == f"no_show:{appointment_id}"
    assert task["type"] == "no_show"
    assert task["appointment_id"] == appointment_id
    assert task["patient_id"] == patient_id
    assert task["requires_validation"] is True
    assert "Patient Test WhatsApp" in task["title"]
    assert task["draft_message"]


def test_ignores_unrelated_appointment():
    now = datetime(
        2026, 8, 16, 10, 0,
        tzinfo=TZ,
    )

    appointments = [
        {
            "id": uuid4(),
            "patient_id": uuid4(),
            "patient_name": "Patient Test",
            "status": "confirmed",
            "start_at": datetime(
                2026, 8, 16, 15, 0,
                tzinfo=TZ,
            ),
        }
    ]

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=now,
    )

    assert actions == []


def test_hides_confirmation_already_sent_by_automatic_copilot():
    appointment_id = uuid4()

    now = datetime(
        2026, 8, 16, 10, 0,
        tzinfo=TZ,
    )

    appointments = [
        {
            "id": appointment_id,
            "patient_id": uuid4(),
            "patient_name": "Patient Test WhatsApp",
            "status": "pending",
            "start_at": datetime(
                2026, 8, 17, 14, 30,
                tzinfo=TZ,
            ),
        }
    ]

    actions = build_appointment_message_actions(
        appointments=appointments,
        now=now,
        sent_confirmation_appointment_ids={
            appointment_id,
        },
    )

    assert actions == []


def test_appointment_action_fields_reach_copilot_task():
    from app.copilot.tasks import (
        build_task_from_recommendation,
    )

    appointment_id = uuid4()
    patient_id = uuid4()

    recommendation = {
        "id": f"confirmation:{appointment_id}",
        "type": "pending_confirmation",
        "priority": "medium",
        "score": 80,
        "title": "Confirmer le rendez-vous",
        "description": "Rendez-vous prévu demain.",
        "recommended_action": "Préparer le message.",
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "draft_message": "Bonjour, confirmez-vous votre rendez-vous ?",
        "reasons": ["Rendez-vous prévu demain"],
        "actions": [],
        "requires_validation": True,
    }

    task = build_task_from_recommendation(
        recommendation
    )

    assert task["patient_id"] == patient_id
    assert task["appointment_id"] == appointment_id
    assert task["type"] == "pending_confirmation"
    assert task["requires_validation"] is True


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    async def execute(self, query, params):
        self.executed.append((query, params))

    async def fetchall(self):
        return self.rows


def test_hydrates_prepared_appointment_message_draft():
    appointment_id = uuid4()
    patient_id = uuid4()
    draft_id = uuid4()

    tasks = [
        {
            "id": f"confirmation:{appointment_id}",
            "type": "pending_confirmation",
            "status": "prepared",
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "draft_id": None,
            "draft_message": (
                "Message généré avant persistance."
            ),
        }
    ]

    cur = FakeCursor(
        [
            {
                "id": draft_id,
                "patient_id": patient_id,
                "appointment_id": appointment_id,
                "message_kind": "pending_confirmation",
                "message": (
                    "Message réellement persisté."
                ),
            }
        ]
    )

    hydrated = asyncio.run(
        hydrate_prepared_appointment_message_drafts(
            cur=cur,
            clinic_id=uuid4(),
            tasks=tasks,
        )
    )

    assert len(hydrated) == 1

    task = hydrated[0]

    assert task["draft_id"] == draft_id
    assert (
        task["draft_message"]
        == "Message réellement persisté."
    )

    assert len(cur.executed) == 1
    query, params = cur.executed[0]

    assert "appointment_message_draft" in query
    assert "message_kind" in query
    assert params[1] == [appointment_id]


def test_does_not_hydrate_open_appointment_task():
    appointment_id = uuid4()

    tasks = [
        {
            "id": f"confirmation:{appointment_id}",
            "type": "pending_confirmation",
            "status": "open",
            "patient_id": uuid4(),
            "appointment_id": appointment_id,
            "draft_id": None,
            "draft_message": "Message initial.",
        }
    ]

    cur = FakeCursor([])

    hydrated = asyncio.run(
        hydrate_prepared_appointment_message_drafts(
            cur=cur,
            clinic_id=uuid4(),
            tasks=tasks,
        )
    )

    assert hydrated == tasks
    assert cur.executed == []
