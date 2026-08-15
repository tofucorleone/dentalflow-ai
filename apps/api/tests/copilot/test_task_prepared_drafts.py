import asyncio
from uuid import uuid4

from app.copilot.tasks import hydrate_prepared_recall_drafts


class DraftCursor:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    async def execute(self, query, params):
        self.query = query
        self.params = params

    async def fetchall(self):
        return self.rows


def test_prepared_recall_uses_latest_audited_draft_message():
    clinic_id = uuid4()
    patient_id = uuid4()
    draft_id = uuid4()

    tasks = [
        {
            "id": f"recall:{patient_id}",
            "type": "recall",
            "patient_id": patient_id,
            "appointment_id": None,
            "status": "prepared",
            "draft_message": "Message généré par le planner",
        }
    ]

    cur = DraftCursor(
        [
            {
                "id": draft_id,
                "patient_id": patient_id,
                "appointment_id": None,
                "message": "Message audité et préparé",
            }
        ]
    )

    result = asyncio.run(
        hydrate_prepared_recall_drafts(
            cur=cur,
            clinic_id=clinic_id,
            tasks=tasks,
        )
    )

    assert result[0]["draft_id"] == draft_id
    assert result[0]["draft_message"] == (
        "Message audité et préparé"
    )

    assert "communication_events" in cur.query
    assert "DISTINCT ON" in cur.query
    assert cur.params == (
        clinic_id,
        [patient_id],
    )


def test_open_recall_does_not_query_drafts():
    clinic_id = uuid4()
    patient_id = uuid4()

    tasks = [
        {
            "id": f"recall:{patient_id}",
            "type": "recall",
            "patient_id": patient_id,
            "appointment_id": None,
            "status": "open",
            "draft_message": "Message planner",
        }
    ]

    cur = DraftCursor([])

    result = asyncio.run(
        hydrate_prepared_recall_drafts(
            cur=cur,
            clinic_id=clinic_id,
            tasks=tasks,
        )
    )

    assert result == tasks
    assert cur.query is None
